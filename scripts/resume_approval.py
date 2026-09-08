from langgraph.types import Command
from scripts.test_high_risk import investigation_graph


if __name__ == "__main__":

    config = {
        "configurable": {
            "thread_id": "high-risk-case-test-002"
        }
    }

    print("=== Human Approval ===")

    decision = input(
        "Enter decision (approve/reject): "
    ).strip().lower()

    while decision not in ["approve", "reject"]:
        print("Invalid decision.")
        decision = input(
            "Enter decision (approve/reject): "
        ).strip().lower()

    result = investigation_graph.invoke(
        Command(resume=decision),
        config=config
    )

    print("\n=== Resumed Investigation ===")
    print(result)