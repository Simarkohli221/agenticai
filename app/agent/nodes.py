from app.db.database import SessionLocal
from app.tools.customer_tool import get_customer_account
from app.tools.transaction_tool import get_transactions
from app.tools.policy_tool import search_policy
from app.risk.risk_engine import analyze_risk
from app.agent.query_parser import parse_investigation_request
from app.agent.llm import generate_investigation_summary, generate_policy_answer
from app.db.database import SessionLocal
from app.tools.case_tool import create_investigation_case
from app.tools.audit_tool import create_audit_log
def parse_request_node(state: dict) -> dict:
    user_request = state["user_request"]

    parsed_request = parse_investigation_request(user_request)

    account_number = parsed_request.get("account_number")

    if not account_number:
        return {
            "error": "Could not identify an account number from the request."
        }

    return {
        "account_number": account_number,
        "intent": parsed_request.get("intent", "INVESTIGATE"),
        "requested_information": parsed_request.get(
            "requested_information",
            ["customer", "transactions", "risk", "policy", "report"],
        ),
    }
def get_customer_node(state: dict) -> dict:
    account_number = state["account_number"]

    db = SessionLocal()

    try:
        customer = get_customer_account(db, account_number)

        if customer is None:
            return {
                "error": f"Account {account_number} not found."
            }

        return {
            "customer": customer
        }

    finally:
        db.close()


def get_transactions_node(state: dict) -> dict:
    account_number = state["account_number"]

    db = SessionLocal()

    try:
        transactions = get_transactions(
            db,
            account_number,
            limit=20
        )

        return {
            "transactions": transactions
        }

    finally:
        db.close()


def build_policy_query(risk_analysis: dict, transactions: list) -> str:
    """
    Deterministically derives a semantic policy-search query from
    the investigation context gathered so far (risk indicators,
    risk level, transaction volume). Pure Python - no LLM involved,
    so the query is reproducible and cannot be influenced by
    prompt-injected text.
    """
    risk_level = risk_analysis.get("risk_level", "LOW")
    indicators = risk_analysis.get("indicators", [])

    indicator_phrases = [
        indicator.get("description") or indicator.get("type", "")
        for indicator in indicators
    ]

    parts = [
        f"Risk level: {risk_level}.",
        f"Transaction count: {len(transactions)}.",
    ]

    if indicator_phrases:
        parts.append("Risk indicators: " + "; ".join(indicator_phrases) + ".")

    if risk_level == "HIGH":
        parts.append(
            "High-risk activity requiring human review and escalation "
            "before any consequential account action."
        )
    elif risk_level == "MEDIUM":
        parts.append("Elevated activity that may warrant additional review.")
    else:
        parts.append("Standard account activity review.")

    return " ".join(parts)


def search_policy_node(state: dict) -> dict:
    risk_analysis = state.get("risk_analysis", {})
    transactions = state.get("transactions", [])

    query = build_policy_query(risk_analysis, transactions)

    try:
        policy_results = search_policy(query)
    except Exception as exc:
        # Policy retrieval failing (e.g. the semantic index has not
        # been built) must never look like "we searched and found no
        # relevant policy" - it is a distinct, reportable failure.
        # generate_report_node/the LLM prompt treat this differently
        # from an empty (but successful) search.
        return {
            "policy_results": [],
            "policy_search_error": str(exc),
        }

    return {
        "policy_results": policy_results,
        "policy_search_error": None,
    }
def analyze_risk_node(state: dict) -> dict:
    transactions = state.get("transactions", [])

    risk_analysis = analyze_risk(transactions)

    return {
        "risk_analysis": risk_analysis,
        "risk_level": risk_analysis["risk_level"],
        "approval_required": risk_analysis["risk_level"] == "HIGH"
    }
def handle_error_node(state: dict) -> dict:
    return {
        "investigation_report": {
            "status": "ERROR",
            "message": state.get(
                "error",
                "Could not identify a valid account number."
            )
        }
    }
def generate_report_node(state: dict) -> dict:
    customer = state.get("customer", {})
    transactions = state.get("transactions", [])
    policy_results = state.get("policy_results", [])
    policy_search_error = state.get("policy_search_error")
    risk_analysis = state.get("risk_analysis", {})

    approval_status = state.get("approval_status")
    risk_level = risk_analysis.get("risk_level")

    if risk_level == "HIGH":
        if approval_status == "approve":
            recommendation = "Investigation approved for continued handling."
        elif approval_status == "reject":
            recommendation = (
                "Investigation rejected by human reviewer. "
                "No consequential action authorized."
            )
        else:
            recommendation = (
                "Human review required before consequential action."
            )

    elif risk_level == "LOW":
        recommendation = "No immediate escalation required."

    else:
        recommendation = "Further review required."

    policy_evidence = [
        {
            "policy": policy["policy"],
            "chunk_id": policy["chunk_id"],
            "excerpt": policy["content"],
        }
        for policy in policy_results
    ]

    policy_citations = [
        f"{policy['policy']} (chunk {policy['chunk_id']})"
        for policy in policy_results
    ]

    evidence = {
        "account": customer.get("account_number"),
        "entity": customer.get("entity_name"),
        "bank": customer.get("bank_name"),
        "transaction_count": len(transactions),
        "risk_level": risk_level,
        "risk_score": risk_analysis.get("risk_score"),
        "risk_indicators": risk_analysis.get("indicators", []),
        "policy_evidence_found": bool(policy_evidence),
        "policy_evidence": policy_evidence,
        "policy_citations": policy_citations,
        "policy_retrieval_unavailable": policy_search_error is not None,
        "approval_status": approval_status,
        "recommendation": recommendation,
    }

    try:
        llm_summary = generate_investigation_summary(evidence)
    except Exception:
        # A narrative-generation failure must never be silently
        # swallowed into a fabricated or misleadingly upbeat report.
        # All of the deterministic evidence above (risk, policy,
        # case status) is already complete and unaffected.
        llm_summary = (
            "A narrative summary could not be generated due to an "
            "LLM generation error. The structured evidence in this "
            "report (risk analysis, policy evidence, and approval "
            "status) was produced by deterministic backend logic and "
            "is unaffected."
        )

    report = {
        **evidence,
        "llm_summary": llm_summary,
    }

    return {
        "investigation_report": report
    }
def create_case_node(state: dict) -> dict:
    account_number = state["account_number"]
    risk_analysis = state.get("risk_analysis", {})

    db = SessionLocal()

    try:
        case = create_investigation_case(
            db=db,
            account_number=account_number,
            risk_level=risk_analysis["risk_level"],
            risk_score=risk_analysis["risk_score"],
        )

        create_audit_log(
            db=db,
            case_id=case["case_id"],
            event_type="CASE_CREATED",
            details=(
                f"Investigation case created for account "
                f"{account_number}. "
                f"Risk level: {risk_analysis['risk_level']}, "
                f"risk score: {risk_analysis['risk_score']}."
            ),
        )

        return {
            "case_id": case["case_id"]
        }

    finally:
        db.close()


def answer_policy_question_node(state: dict) -> dict:
    """
    Lightweight path for a POLICY_QUESTION-intent request (see
    app/agent/planner.py and app/agent/routing.py). Answers a policy
    question grounded in retrieved policy evidence only - it does
    NOT run risk analysis, does NOT create an investigation case, and
    never touches HITL. This is a read-only informational response,
    not a risk assessment or investigation finding.
    """
    customer = state.get("customer", {})
    user_request = state.get("user_request", "")

    try:
        policy_results = search_policy(user_request)
        policy_search_error = None
    except Exception as exc:
        policy_results = []
        policy_search_error = str(exc)

    policy_evidence = [
        {
            "policy": policy["policy"],
            "chunk_id": policy["chunk_id"],
            "excerpt": policy["content"],
        }
        for policy in policy_results
    ]

    policy_citations = [
        f"{policy['policy']} (chunk {policy['chunk_id']})"
        for policy in policy_results
    ]

    evidence = {
        "account": customer.get("account_number"),
        "entity": customer.get("entity_name"),
        "bank": customer.get("bank_name"),
        "question": user_request,
        "policy_evidence_found": bool(policy_evidence),
        "policy_evidence": policy_evidence,
        "policy_citations": policy_citations,
        "policy_retrieval_unavailable": policy_search_error is not None,
    }

    try:
        llm_summary = generate_policy_answer(evidence)
    except Exception:
        llm_summary = (
            "A narrative answer could not be generated due to an LLM "
            "generation error. Any retrieved policy evidence is "
            "listed above and is unaffected."
        )

    report = {
        "status": "POLICY_ANSWER",
        **evidence,
        "llm_summary": llm_summary,
    }

    return {
        "investigation_report": report
    }