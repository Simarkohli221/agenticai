from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    String,
    DateTime,
    Numeric,
    Boolean,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )

    from_bank: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    from_account: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("accounts.account_number"),
        nullable=False
    )

    to_bank: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    to_account: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("accounts.account_number"),
        nullable=False
    )

    amount_received: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False
    )

    receiving_currency: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False
    )

    payment_currency: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    payment_format: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    is_laundering: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False
    )


Index(
    "idx_transactions_from_account",
    Transaction.from_account
)

Index(
    "idx_transactions_to_account",
    Transaction.to_account
)

Index(
    "idx_transactions_timestamp",
    Transaction.timestamp
)

Index(
    "idx_transactions_account_timestamp",
    Transaction.from_account,
    Transaction.timestamp
)