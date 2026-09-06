from app.agent.llm import generate_investigation_summary


if __name__ == "__main__":

    evidence = {
        "account": "8000EBD30",
        "entity": "Partnership #1",
        "risk_level": "LOW",
        "risk_score": 20,
        "risk_indicators": [
            {
                "type": "MULTIPLE_COUNTERPARTIES",
                "description": "Activity involved 14 distinct accounts."
            }
        ],
        "policy": "AML Transaction Monitoring Policy",
        "transaction_count": 15
    }

    summary = generate_investigation_summary(evidence)

    print("=== Gemini Investigation Summary ===")
    print(summary)