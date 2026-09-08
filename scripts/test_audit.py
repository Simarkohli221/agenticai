from app.db.database import SessionLocal
from sqlalchemy import select

from app.models.audit import AuditLog


if __name__ == "__main__":
    db = SessionLocal()

    try:
        logs = db.execute(
            select(AuditLog)
            .where(AuditLog.case_id == 11)
            .order_by(AuditLog.created_at)
        ).scalars().all()

        print("=== Audit Logs for Case 11 ===")

        for log in logs:
            print({
                "audit_id": log.audit_id,
                "case_id": log.case_id,
                "event_type": log.event_type,
                "details": log.details,
                "created_at": log.created_at.isoformat(),
            })

    finally:
        db.close()