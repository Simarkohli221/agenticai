from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Entity(Base):
    __tablename__ = "entities"

    entity_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    entity_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    accounts = relationship(
        "Account",
        back_populates="entity"
    )