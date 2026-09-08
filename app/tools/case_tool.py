from sqlalchemy.orm import Session
from app.models.case import InvestigationCase


ALLOWED_STATUSES = {
    "OPEN",
    "UNDER_REVIEW",
    "APPROVED",
    "REJECTED",
    "CLOSED",
}


def create_investigation_case(
    db: Session,
    account_number: str,
    risk_level: str,
    risk_score: int,
) -> dict:
    case = InvestigationCase(
        account_number=account_number,
        risk_level=risk_level,
        risk_score=risk_score,
        status="OPEN",
    )

    db.add(case)
    db.commit()
    db.refresh(case)

    return {
        "case_id": case.case_id,
        "account_number": case.account_number,
        "risk_level": case.risk_level,
        "risk_score": case.risk_score,
        "status": case.status,
        "created_at": case.created_at.isoformat(),
    }


def get_case(
    db: Session,
    case_id: int,
) -> dict | None:

    case = db.get(InvestigationCase, case_id)

    if case is None:
        return None

    return {
        "case_id": case.case_id,
        "account_number": case.account_number,
        "risk_level": case.risk_level,
        "risk_score": case.risk_score,
        "status": case.status,
        "created_at": case.created_at.isoformat(),
        "thread_id": case.thread_id,
    }


def set_case_thread_id(
    db: Session,
    case_id: int,
    thread_id: str,
    commit: bool = True,
) -> None:

    case = db.get(InvestigationCase, case_id)

    if case is None:
        return

    case.thread_id = thread_id

    if commit:
        db.commit()
    else:
        # Participating in a transaction the caller owns: make the
        # change visible within it without ending it.
        db.flush()


def update_case_status(
    db: Session,
    case_id: int,
    new_status: str,
    commit: bool = True,
) -> dict | None:

    if new_status not in ALLOWED_STATUSES:
        raise ValueError(
            f"Invalid case status: {new_status}. "
            f"Allowed statuses: {sorted(ALLOWED_STATUSES)}"
        )

    case = db.get(InvestigationCase, case_id)

    if case is None:
        return None

    case.status = new_status

    if commit:
        db.commit()
        db.refresh(case)
    else:
        # Participating in a transaction the caller owns: flush so
        # the update is visible within it, but leave it open for the
        # caller to commit or roll back as a unit.
        db.flush()

    return {
        "case_id": case.case_id,
        "account_number": case.account_number,
        "risk_level": case.risk_level,
        "risk_score": case.risk_score,
        "status": case.status,
        "created_at": case.created_at.isoformat(),
    }