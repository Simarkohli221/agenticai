from app.tools.policy_tool import search_policy


if __name__ == "__main__":
    results = search_policy(
        "suspicious transaction high risk human review"
    )

    for result in results:
        print("Policy:", result["policy"])
        print("Score:", result["score"])
        print("Content:")
        print(result["content"])