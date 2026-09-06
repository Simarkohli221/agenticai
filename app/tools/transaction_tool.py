from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models.transaction import Transaction


def get_transactions(
    db: Session,
    account_number: str,
    limit: int = 20
) -> list[dict]:

    query = (
        select(Transaction)
        .where(
            or_(
                Transaction.from_account == account_number,
                Transaction.to_account == account_number
            )
        )
        .order_by(Transaction.timestamp.desc())
        .limit(limit)
    )

    transactions = db.execute(query).scalars().all()

    return [
        {
            "transaction_id": transaction.transaction_id,
            "timestamp": transaction.timestamp.isoformat(),
            "from_bank": transaction.from_bank,
            "from_account": transaction.from_account,
            "to_bank": transaction.to_bank,
            "to_account": transaction.to_account,
            "amount_received": float(transaction.amount_received),
            "receiving_currency": transaction.receiving_currency,
            "amount_paid": float(transaction.amount_paid),
            "payment_currency": transaction.payment_currency,
            "payment_format": transaction.payment_format,
            "is_laundering": transaction.is_laundering,
        }
        for transaction in transactions
    ]