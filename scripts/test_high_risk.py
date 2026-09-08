import sqlite3

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.agent.state import InvestigationState
from app.agent.nodes import (
    create_case_node,
    get_customer_node,
    get_transactions_node,
    search_policy_node,
    generate_report_node,
)
from app.agent.approval import human_approval_node
from app.agent.test_nodes import force_high_risk_node
from app.agent.routing import route_by_risk


# SQLite checkpointer
connection = sqlite3.connect(
    "D:/Banking_Data/high_risk_test.db",
    check_same_thread=False
)

checkpointer = SqliteSaver(connection)
checkpointer.setup()


# Create graph
graph = StateGraph(InvestigationState)


# Add nodes
graph.add_node("get_customer", get_customer_node)
graph.add_node("get_transactions", get_transactions_node)
graph.add_node("search_policy", search_policy_node)
graph.add_node("force_high_risk", force_high_risk_node)
graph.add_node("create_case", create_case_node)
graph.add_node("human_approval", human_approval_node)
graph.add_node("generate_report", generate_report_node)


# Main flow
graph.add_edge(START, "get_customer")
graph.add_edge("get_customer", "get_transactions")
graph.add_edge("get_transactions", "search_policy")
graph.add_edge("search_policy", "force_high_risk")

# IMPORTANT:
# The case must be created BEFORE human approval.
graph.add_edge("force_high_risk", "create_case")


# Route based on risk after the case has been created
graph.add_conditional_edges(
    "create_case",
    route_by_risk,
    {
        "low_risk": "generate_report",
        "high_risk": "human_approval",
    }
)


# After human approval
graph.add_edge("human_approval", "generate_report")


# Finish after report generation
graph.add_edge("generate_report", END)


# Compile graph
investigation_graph = graph.compile(
    checkpointer=checkpointer
)


if __name__ == "__main__":

    initial_state = {
        "account_number": "8000EBD30"
    }

    config = {
        "configurable": {
            "thread_id": "high-risk-case-test-002"
        }
    }

    result = investigation_graph.invoke(
        initial_state,
        config=config
    )

    print("=== Result ===")
    print(result)