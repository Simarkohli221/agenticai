from app.agent.nodes import (
    get_transactions_node,
    analyze_risk_node
)


if __name__ == "__main__":
    state = {
        "account_number": "8000EBD30"
    }

    transaction_result = get_transactions_node(state)

    state.update(transaction_result)

    risk_result = analyze_risk_node(state)

    print("=== Risk Node Result ===")
    print(risk_result)