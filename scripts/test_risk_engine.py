from app.db.database import SessionLocal
from app.tools.transaction_tool import get_transactions
from app.risk.risk_engine import analyze_risk


if __name__ == "__main__":
    db = SessionLocal()

    try:
        transactions = get_transactions(
            db,
            "8000EBD30",
            limit=20
        )

        result = analyze_risk(transactions)

        print("=== Risk Analysis ===")
        print("Risk Level:", result["risk_level"])
        print("Risk Score:", result["risk_score"])
        print("Transaction Count:", result["transaction_count"])

        print("\n=== Indicators ===")

        for indicator in result["indicators"]:
            print(
                f"- {indicator['type']}: "
                f"{indicator['description']}"
            )

    finally:
        db.close()  