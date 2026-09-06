import sqlite3

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.agent.state import InvestigationState
from app.agent.routing import route_by_risk, route_after_parsing
from app.agent.nodes import (
    parse_request_node,
    handle_error_node,
    get_customer_node,
    get_transactions_node,
    search_policy_node,
    analyze_risk_node,
    generate_report_node,
    create_case_node
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
    graph.add_edge("get_customer", "get_transactions")
    graph.add_edge("get_transactions", "search_policy")
    graph.add_edge("search_policy", "analyze_risk")

    # Risk-based routing
    graph.add_edge("analyze_risk", "create_case")
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

    # SQLite checkpointer
    connection = sqlite3.connect(
        "D:/Banking_Data/langgraph_checkpoints.db",
        check_same_thread=False
    )

    checkpointer = SqliteSaver(connection)
    checkpointer.setup()

    return graph.compile(
        checkpointer=checkpointer
    )


investigation_graph = build_investigation_graph()