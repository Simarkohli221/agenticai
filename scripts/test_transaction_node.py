from app.agent.nodes import get_transactions_node


if __name__ == "__main__":
    state = {
        "account_number": "8000EBD30"
    }

    result = get_transactions_node(state)

    print("=== Transaction Node Result ===")
    print("Transaction count:", len(result["transactions"]))

    for transaction in result["transactions"][:5]:
        print(transaction)