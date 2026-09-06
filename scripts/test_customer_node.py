from app.agent.nodes import get_customer_node


if __name__ == "__main__":
    state = {
        "account_number": "8000EBD30"
    }

    result = get_customer_node(state)

    print("=== Node Result ===")
    print(result)