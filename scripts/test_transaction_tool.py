from app.db.database import SessionLocal
from app.tools.transaction_tool import get_transactions


if __name__ == "__main__":
    db = SessionLocal()

    try:
        transactions = get_transactions(
            db,
            "8000EBD30",
            limit=10
        )

        print(f"Found {len(transactions)} transactions")

        for transaction in transactions:
            print(transaction)

    finally:
        db.close()