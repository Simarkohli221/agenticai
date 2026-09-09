import os
import sqlite3

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.agent.state import InvestigationState
from app.agent.routing import (
    route_by_risk,
    route_after_parsing,
    route_after_customer_lookup,
)
from app.agent.nodes import (
    parse_request_node,
    handle_error_node,
    get_customer_node,
    get_transactions_node,
    search_policy_node,
    analyze_risk_node,
    generate_report_node,
    create_case_node,
    answer_policy_question_node,
)
from app.agent.routing import route_by_risk
from app.agent.approval import human_approval_node


def build_investigation_graph():

    graph = StateGraph(InvestigationState)

    # Add nodes
    graph.add_node("get_customer", get_customer_node)
    graph.add_node("get_transactions", get_transactions_node)
    graph.add_node("search_policy", search_policy_node)
    graph.add_node("analyze_risk", analyze_risk_node)
    graph.add_node("generate_report", generate_report_node)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("parse_request", parse_request_node)
    graph.add_node("handle_error", handle_error_node)
    graph.add_node("create_case", create_case_node)
    graph.add_node("answer_policy_question", answer_policy_question_node)

    # Main investigation flow
    graph.add_edge(START, "parse_request")

    graph.add_conditional_edges(
        "parse_request",
        route_after_parsing,
        {
            "continue": "get_customer",
            "error": "handle_error",
        }
    )

    graph.add_edge("handle_error", END)

    # Fork on the request's classified intent (see app/agent/planner.py):
    # a POLICY_QUESTION goes to the lightweight, case-free policy-only
    # path; everything else goes through the full investigation path.
    graph.add_conditional_edges(
        "get_customer",
        route_after_customer_lookup,
        {
            "full_investigation": "get_transactions",
            "policy_only": "answer_policy_question",
            "error": "handle_error",
        }
    )

    graph.add_edge("answer_policy_question", END)

    # analyze_risk runs before search_policy so the policy query can
    # be derived from the actual risk indicators/level (semantic
    # RAG), rather than a fixed keyword string.
    graph.add_edge("get_transactions", "analyze_risk")
    graph.add_edge("analyze_risk", "search_policy")

    # Risk-based routing
    graph.add_edge("search_policy", "create_case")
    graph.add_conditional_edges(
        "create_case",
        route_by_risk,
        {
            "low_risk": "generate_report",
            "high_risk": "human_approval",
        }
    )

    # End points
    graph.add_edge("generate_report", END)
    graph.add_edge("human_approval", "generate_report")

    # SQLite checkpointer - overridable for test isolation (see
    # scripts/test_e2e.py); default is unchanged for every existing
    # caller that doesn't set this environment variable.
    checkpoint_path = os.getenv(
        "LANGGRAPH_CHECKPOINT_DB", "D:/Banking_Data/langgraph_checkpoints.db"
    )

    connection = sqlite3.connect(
        checkpoint_path,
        check_same_thread=False
    )

    checkpointer = SqliteSaver(connection)
    checkpointer.setup()

    return graph.compile(
        checkpointer=checkpointer
    )


investigation_graph = build_investigation_graph()