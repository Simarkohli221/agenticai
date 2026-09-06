from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.entity import Entity


def get_customer_account(
    db: Session,
    account_number: str
) -> dict | None:

    result = db.execute(
        select(Account, Entity)
        .join(
            Entity,
            Account.entity_id == Entity.entity_id
        )
        .where(
            Account.account_number == account_number
        )
    ).first()

    if result is None:
        return None

    account, entity = result

    return {
        "account_number": account.account_number,
        "bank_id": account.bank_id,
        "bank_name": account.bank_name,
        "entity_id": entity.entity_id,
        "entity_name": entity.entity_name,
    }