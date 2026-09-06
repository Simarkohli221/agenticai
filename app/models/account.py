from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Account(Base):
    __tablename__ = "accounts"

    account_number: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    bank_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    bank_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    entity_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("entities.entity_id"),
        nullable=False
    )

    entity = relationship(
        "Entity",
        back_populates="accounts"
    )