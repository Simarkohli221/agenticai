from app.agent.graph import investigation_graph


if __name__ == "__main__":

    initial_state = {
        "user_request": "Analyze this account for suspicious activity"
    }

    config = {
        "configurable": {
            "thread_id": "invalid-query-test-001"
        }
    }

    result = investigation_graph.invoke(
        initial_state,
        config=config
    )

    print("=== Result ===")
    print(result)