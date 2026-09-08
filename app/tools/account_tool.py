from sqlalchemy.orm import Session

from app.models.account import Account


ALLOWED_ACCOUNT_STATUSES = {
    "ACTIVE",
    "REVIEW",
    "FROZEN",
    "CLOSED",
}

# Suggested safe transitions only - deliberately narrow. CLOSED is
# terminal: no further transitions are permitted out of it.
ALLOWED_STATUS_TRANSITIONS = {
    "ACTIVE": {"REVIEW", "FROZEN", "CLOSED"},
    "REVIEW": {"ACTIVE", "FROZEN"},
    "FROZEN": {"REVIEW"},
    "CLOSED": set(),
}


def get_account(
    db: Session,
    account_number: str,
) -> dict | None:

    account = db.get(Account, account_number)

    if account is None:
        return None

    return {
        "account_number": account.account_number,
        "bank_id": account.bank_id,
        "bank_name": account.bank_name,
        "entity_id": account.entity_id,
        "status": account.status,
    }


def update_account_status(
    db: Session,
    account_number: str,
    new_status: str,
    commit: bool = True,
) -> dict | None:
    """
    Narrowly scoped: changes only the `status` field of one account.
    Never accepts arbitrary fields, raw SQL, or bulk updates.
    """

    if new_status not in ALLOWED_ACCOUNT_STATUSES:
        raise ValueError(
            f"Invalid account status: {new_status}. "
            f"Allowed statuses: {sorted(ALLOWED_ACCOUNT_STATUSES)}"
        )

    account = db.get(Account, account_number)

    if account is None:
        return None

    account.status = new_status

    if commit:
        db.commit()
        db.refresh(account)
    else:
        # Participating in a transaction the caller owns: flush so
        # the update is visible within it, but leave it open for the
        # caller to commit or roll back as a unit.
        db.flush()

    return {
        "account_number": account.account_number,
        "bank_id": account.bank_id,
        "bank_name": account.bank_name,
        "entity_id": account.entity_id,
        "status": account.status,
    }
