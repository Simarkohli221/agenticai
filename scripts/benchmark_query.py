import time

from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.transaction import Transaction


TEST_ACCOUNT = "8000EBD30"


def benchmark():
    db = SessionLocal()

    try:
        start = time.perf_counter()

        transactions = db.scalars(
            select(Transaction)
            .where(
                (Transaction.from_account == TEST_ACCOUNT)
                | (Transaction.to_account == TEST_ACCOUNT)
            )
            .order_by(Transaction.timestamp.desc())
            .limit(100)
        ).all()

        elapsed = time.perf_counter() - start

        print("=== Query Benchmark ===")
        print("Account:", TEST_ACCOUNT)
        print("Transactions returned:", len(transactions))
        print(f"Query time: {elapsed:.4f} seconds")

    finally:
        db.close()


if __name__ == "__main__":
    benchmark()