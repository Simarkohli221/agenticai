from app.agent.graph import investigation_graph


if __name__ == "__main__":

    initial_state = {
        "account_number": "8000EBD30"
    }

    config = {
        "configurable": {
            "thread_id": "test-investigation-001"
        }
    }

    result = investigation_graph.invoke(
        initial_state,
        config=config
    )

    print("=== Investigation Complete ===")

    print("\nAccount:")
    print(result["account_number"])

    print("\nCustomer:")
    print(result["customer"])

    print("\nTransactions:")
    print(len(result["transactions"]))

    print("\nPolicies:")
    print(len(result["policy_results"]))

    print("\nRisk:")
    print(result["risk_analysis"])

    print("\nApproval Required:")
    print(result["approval_required"])

    print("\n=== Investigation Report ===")
    print(result["investigation_report"])