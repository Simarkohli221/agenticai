"""
Tests Step 12 agent orchestration: intent classification, deterministic
tool-selection planning, conditional graph routing, tool-failure
handling, and the account-action security boundary.

Cost discipline: tests that only need to prove routing/state/failure
behavior use direct node calls with monkeypatched dependencies (zero
Groq calls). Only tests that must exercise the real end-to-end graph
make real Groq calls, and each such call is used to cover as many
assertions as possible (see comments below).
"""

import uuid
import inspect

import app.agent.nodes as nodes
from app.agent.graph import investigation_graph
from app.agent.planner import plan_tools, ALLOWED_TOOLS, INVESTIGATE, POLICY_QUESTION, TRANSACTION_QUESTION
from app.agent.routing import route_after_customer_lookup, route_by_risk
from app.agent.query_parser import parse_investigation_request
from app.agent.nodes import search_policy_node, generate_report_node
from app.services.investigation_service import run_investigation
from app.risk.risk_engine import analyze_risk
from app.tools.policy_tool import search_policy
from app.rag.policy_rag import METADATA_FILE
import json

KNOWN_ACCOUNT = "8000EBD30"


def result_label(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def run_full_graph(user_request: str) -> dict:
    config = {"configurable": {"thread_id": f"orchestration-test-{uuid.uuid4()}"}}
    return investigation_graph.invoke({"user_request": user_request}, config=config)


def citations_are_traceable(policy_evidence: list) -> bool:
    if not policy_evidence:
        return True
    persisted = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
    lookup = {(e["policy"], e["chunk_id"]): e["content"] for e in persisted}
    return all(
        lookup.get((item["policy"], item["chunk_id"])) == item["excerpt"]
        for item in policy_evidence
    )


if __name__ == "__main__":
    print("=== Deterministic tests (no LLM) ===")

    # 7. Correct tool/data path selected (planner + routing, no LLM)
    policy_plan = plan_tools(POLICY_QUESTION)
    investigate_plan = plan_tools(INVESTIGATE)
    txn_plan = plan_tools(TRANSACTION_QUESTION)
    unknown_plan = plan_tools("SOMETHING_UNRECOGNIZED")

    test7_passed = (
        "get_transactions" not in policy_plan
        and "analyze_risk" not in policy_plan
        and "get_transactions" in investigate_plan
        and "analyze_risk" in investigate_plan
        and "get_transactions" in txn_plan
        and unknown_plan == investigate_plan  # unknown intent -> safe default
        and all(tool in ALLOWED_TOOLS for tool in investigate_plan)
    )
    print("Correct tool/data path selected by plan_tools:", result_label(test7_passed))

    routing_policy_only = route_after_customer_lookup(
        {"customer": {"account_number": KNOWN_ACCOUNT}, "intent": POLICY_QUESTION}
    )
    routing_full = route_after_customer_lookup(
        {"customer": {"account_number": KNOWN_ACCOUNT}, "intent": INVESTIGATE}
    )
    routing_error = route_after_customer_lookup({"error": "boom"})
    test7b_passed = (
        routing_policy_only == "policy_only"
        and routing_full == "full_investigation"
        and routing_error == "error"
    )
    print("Graph routing matches the tool plan:", result_label(test7b_passed))

    # 11. Deterministic risk engine controls routing
    high_risk_result = analyze_risk([
        {
            "amount_received": 50000, "from_account": "A", "to_account": "B",
            "is_laundering": True,
        }
    ])
    test11_passed = (
        route_by_risk({"risk_level": high_risk_result["risk_level"]})
        == ("high_risk" if high_risk_result["risk_level"] == "HIGH" else "low_risk")
        and route_by_risk({"risk_level": "HIGH"}) == "high_risk"
        and route_by_risk({"risk_level": "LOW"}) == "low_risk"
        and route_by_risk({}) == "low_risk"
    )
    print("Deterministic risk engine controls routing:", result_label(test11_passed))

    # 12. Tool failure handled safely (search_policy monkeypatched to raise)
    original_search_policy = nodes.search_policy

    def failing_search_policy(query, top_k=5):
        raise RuntimeError("simulated policy retrieval failure")

    nodes.search_policy = failing_search_policy
    try:
        result = search_policy_node({"risk_analysis": {"risk_level": "LOW"}, "transactions": []})
    finally:
        nodes.search_policy = original_search_policy

    test12_passed = (
        result["policy_results"] == []
        and result["policy_search_error"] is not None
    )
    print("Tool failure (policy retrieval) handled safely:", result_label(test12_passed))

    # 13. Missing policy evidence does not cause fabricated policy
    # (generate_investigation_summary monkeypatched - no real LLM call)
    original_llm_summary = nodes.generate_investigation_summary
    captured_evidence = {}

    def stub_summary(evidence):
        captured_evidence.update(evidence)
        return "stub summary"

    nodes.generate_investigation_summary = stub_summary
    try:
        report = generate_report_node({
            "customer": {"account_number": KNOWN_ACCOUNT},
            "transactions": [],
            "policy_results": [],
            "policy_search_error": None,
            "risk_analysis": {"risk_level": "LOW", "risk_score": 0, "indicators": []},
        })["investigation_report"]
    finally:
        nodes.generate_investigation_summary = original_llm_summary

    test13_passed = (
        report["policy_evidence_found"] is False
        and report["policy_evidence"] == []
        and report["policy_retrieval_unavailable"] is False
    )
    print("Missing policy evidence does not fabricate policy:", result_label(test13_passed))

    # Distinguish "no evidence found" from "retrieval failed"
    nodes.generate_investigation_summary = stub_summary
    try:
        report_failed = generate_report_node({
            "customer": {"account_number": KNOWN_ACCOUNT},
            "transactions": [],
            "policy_results": [],
            "policy_search_error": "index missing",
            "risk_analysis": {"risk_level": "LOW", "risk_score": 0, "indicators": []},
        })["investigation_report"]
    finally:
        nodes.generate_investigation_summary = original_llm_summary

    test13b_passed = report_failed["policy_retrieval_unavailable"] is True
    print(
        "Policy retrieval failure distinguished from empty result:",
        result_label(test13b_passed),
    )

    # 14. LLM failure handled safely (generate_investigation_summary raises)
    def raising_summary(evidence):
        raise RuntimeError("simulated LLM failure")

    nodes.generate_investigation_summary = raising_summary
    try:
        report_llm_fail = generate_report_node({
            "customer": {"account_number": KNOWN_ACCOUNT},
            "transactions": [],
            "policy_results": [],
            "policy_search_error": None,
            "risk_analysis": {"risk_level": "LOW", "risk_score": 0, "indicators": []},
        })["investigation_report"]
    finally:
        nodes.generate_investigation_summary = original_llm_summary

    test14_passed = (
        "llm_summary" in report_llm_fail
        and "error" in report_llm_fail["llm_summary"].lower()
        and report_llm_fail["risk_level"] == "LOW"  # deterministic evidence intact
    )
    print("LLM generation failure handled safely:", result_label(test14_passed))

    # 19/20. Account actions cannot be reached from the agent/LLM side.
    # Checked via the AST (real import/call statements only) so that
    # explanatory prose in comments/docstrings - e.g. this very test
    # file, or planner.py's docstring, mentioning "account_service" in
    # plain English - can never produce a false failure or a false pass.
    import ast

    def module_imports(module) -> set:
        tree = ast.parse(inspect.getsource(module))
        imported = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        return imported

    import app.agent.nodes as agent_nodes_module
    import app.agent.graph as agent_graph_module
    import app.agent.planner as agent_planner_module

    forbidden_modules = {
        "app.services.account_service",
        "app.tools.account_tool",
    }

    all_agent_imports = (
        module_imports(agent_nodes_module)
        | module_imports(agent_graph_module)
        | module_imports(agent_planner_module)
    )

    test19_passed = all_agent_imports.isdisjoint(forbidden_modules)
    print(
        "Account actions unreachable from agent/graph/planner code:",
        result_label(test19_passed),
    )

    # HITL (human_approval_node, app/agent/approval.py) is only ever
    # wired in as a LangGraph node via the graph's own edges - the
    # planner and the ordinary tool-executing nodes have no import of
    # it at all, so neither can invoke or bypass it directly.
    test20_passed = "app.agent.approval" not in (
        module_imports(agent_planner_module) | module_imports(agent_nodes_module)
    )
    print(
        "HITL cannot be bypassed via the planner/nodes:",
        result_label(test20_passed),
    )

    # 21. thread_id remains server-controlled (not an input to the service)
    run_investigation_params = inspect.signature(run_investigation).parameters
    test21_passed = "thread_id" not in run_investigation_params
    print("thread_id is not client-controllable:", result_label(test21_passed))

    print()
    print("=== Request-understanding tests (parser only, no full graph run) ===")

    # 4. Natural-language variations (parse only - 1 Groq call each)
    variations = [
        f"Analyze account {KNOWN_ACCOUNT}.",
        f"Review the recent transactions for account {KNOWN_ACCOUNT} and explain the risks.",
        f"Which AML policy applies to the suspicious activity for account {KNOWN_ACCOUNT}?",
    ]
    variation_results = [parse_investigation_request(q) for q in variations]
    test4_passed = all(
        r.get("account_number") == KNOWN_ACCOUNT and r.get("intent") in
        {INVESTIGATE, POLICY_QUESTION, TRANSACTION_QUESTION}
        for r in variation_results
    )
    print("Natural-language variations parsed correctly:", result_label(test4_passed))

    # 5. Invalid/missing account -> controlled error, not a guess
    missing_account_result = run_full_graph("Please look into this for me.")
    test5_passed = (
        missing_account_result.get("investigation_report", {}).get("status") == "ERROR"
        and "account_id" not in missing_account_result
    )
    print("Missing account handled as controlled error:", result_label(test5_passed))

    # 6. Unsupported request handled safely (no account, unrelated topic)
    unsupported_result = run_full_graph("What is the weather like today?")
    test6_passed = (
        unsupported_result.get("investigation_report", {}).get("status") == "ERROR"
    )
    print("Unsupported request handled safely:", result_label(test6_passed))

    print()
    print("=== Full-graph tests (real Groq calls) ===")

    # 1, 9, 15, 16, 17: simple investigation query, LOW-risk (known
    # account) skips HITL, tools called exactly once, state/case_id
    # survive across nodes.
    call_counts = {"search_policy": 0}
    original_search_policy_tool = nodes.search_policy

    def counting_search_policy(query, top_k=5):
        call_counts["search_policy"] += 1
        return original_search_policy_tool(query, top_k=top_k)

    nodes.search_policy = counting_search_policy
    try:
        result1 = run_full_graph(
            f"Investigate account {KNOWN_ACCOUNT} for suspicious activity."
        )
    finally:
        nodes.search_policy = original_search_policy_tool

    report1 = result1.get("investigation_report", {})
    test1_passed = (
        result1.get("intent") in {INVESTIGATE, TRANSACTION_QUESTION}
        and result1.get("account_number") == KNOWN_ACCOUNT
        and "customer" in result1
        and "transactions" in result1
        and "risk_analysis" in result1
        and "case_id" in result1
        and report1.get("status") != "ERROR"
    )
    print("Simple investigation query completes with full state:", result_label(test1_passed))

    test9_passed = "__interrupt__" not in result1 and result1["risk_level"] != "HIGH"
    print("LOW/MEDIUM-risk route skips HITL:", result_label(test9_passed))

    test15_passed = call_counts["search_policy"] == 1
    print("Tool execution bounded (search_policy called once):", result_label(test15_passed))

    test22a_passed = citations_are_traceable(report1.get("policy_evidence", []))
    print("Full-investigation citations are traceable:", result_label(test22a_passed))

    # 2. Transaction-focused query (still a full investigation path)
    result2 = run_full_graph(
        f"Review the recent transactions for account {KNOWN_ACCOUNT} and explain the risks."
    )
    report2 = result2.get("investigation_report", {})
    test2_passed = (
        "transactions" in result2
        and "risk_analysis" in result2
        and report2.get("status") != "ERROR"
    )
    print("Transaction-focused query uses full investigation path:", result_label(test2_passed))

    # 3, 8, 22b: policy-focused query - no case, no risk, grounded answer
    result3 = run_full_graph(
        f"Which AML policy applies to the suspicious activity for account {KNOWN_ACCOUNT}?"
    )
    report3 = result3.get("investigation_report", {})
    test3_passed = (
        result3.get("intent") == POLICY_QUESTION
        and "case_id" not in result3
        and "risk_analysis" not in result3
        and report3.get("status") == "POLICY_ANSWER"
        and report3.get("policy_evidence_found") is True
    )
    print("Policy-focused query uses lightweight path (no case/risk):", result_label(test3_passed))

    test8_passed = len(report3.get("policy_citations", [])) > 0
    print("Policy retrieval integrated into policy-only path:", result_label(test8_passed))

    test22b_passed = citations_are_traceable(report3.get("policy_evidence", []))
    print("Policy-only citations are traceable:", result_label(test22b_passed))

    # 10, 18: HIGH-risk route enters HITL; approval status survives
    # into the final report. Uses the existing controlled
    # force_high_risk test harness (zero LLM calls to create the
    # pending case; one real Groq call for the post-approval report).
    from scripts.test_secure_hitl import (
        build_high_risk_test_graph,
        create_pending_high_risk_case,
    )
    from langgraph.types import Command

    test_graph = build_high_risk_test_graph()
    high_risk_case_id, thread_id = create_pending_high_risk_case(test_graph)

    config = {"configurable": {"thread_id": thread_id}}
    resumed_result = investigation_graph.invoke(
        Command(resume="approve"), config=config
    )

    test10_passed = resumed_result.get("case_id") == high_risk_case_id
    print("HIGH-risk case resumes through the real investigation graph:", result_label(test10_passed))

    test18_passed = (
        resumed_result.get("approval_status") == "approve"
        and resumed_result.get("investigation_report", {}).get("approval_status") == "approve"
    )
    print("Approval status preserved into final report:", result_label(test18_passed))
