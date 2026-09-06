from app.agent.nodes import search_policy_node


if __name__ == "__main__":
    state = {
        "account_number": "8000EBD30"
    }

    result = search_policy_node(state)

    print("=== Policy Node Result ===")
    print("Policies found:", len(result["policy_results"]))

    for policy in result["policy_results"]:
        print("\nPolicy:", policy["policy"])
        print("Score:", policy["score"])