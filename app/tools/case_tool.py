from sqlalchemy.orm import Session

from app.models.case import InvestigationCase


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