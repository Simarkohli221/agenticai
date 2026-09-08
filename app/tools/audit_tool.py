from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def create_audit_log(
    db: Session,
    event_type: str,
    details: str,
    case_id: int | None = None,
    commit: bool = True,
) -> dict:

    audit = AuditLog(
        case_id=case_id,
        event_type=event_type,
        details=details,
    )

    db.add(audit)

    if commit:
        db.commit()
        db.refresh(audit)
    else:
        # Participating in a transaction the caller owns: flush so
        # the row (and its generated audit_id) is visible within it,
        # but leave the transaction open for the caller to finish.
        db.flush()

    return {
        "audit_id": audit.audit_id,
        "case_id": audit.case_id,
        "event_type": audit.event_type,
        "details": audit.details,
        "created_at": audit.created_at.isoformat(),
    }


def has_audit_event(
    db: Session,
    case_id: int,
    event_type: str,
) -> bool:

    result = db.execute(
        select(AuditLog.audit_id)
        .where(
            AuditLog.case_id == case_id,
            AuditLog.event_type == event_type,
        )
        .limit(1)
    ).first()

    return result is not None