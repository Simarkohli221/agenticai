from sqlalchemy import func, select

from app.db.database import SessionLocal
from app.models.entity import Entity
from app.models.account import Account
from app.models.transaction import Transaction


def verify_data():
    db = SessionLocal()

    try:
        entity_count = db.scalar(
            select(func.count()).select_from(Entity)
        )

        account_count = db.scalar(
            select(func.count()).select_from(Account)
        )

        transaction_count = db.scalar(
            select(func.count()).select_from(Transaction)
        )

        laundering_count = db.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.is_laundering.is_(True))
        )

        print("=== Database Verification ===")
        print("Entities:", entity_count)
        print("Accounts:", account_count)
        print("Transactions:", transaction_count)
        print("Laundering transactions:", laundering_count)

    finally:
        db.close()


if __name__ == "__main__":
    verify_data()