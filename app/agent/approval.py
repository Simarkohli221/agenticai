from langgraph.types import interrupt

from app.db.database import SessionLocal
from app.tools.case_tool import update_case_status
from app.tools.audit_tool import create_audit_log, has_audit_event

def human_approval_node(state: dict) -> dict:
    risk_analysis = state.get("risk_analysis", {})
    customer = state.get("customer", {})
    case_id = state.get("case_id")

    approval_request = {
        "message": "High-risk investigation requires human approval.",
        "case_id": case_id,
        "account_number": customer.get("account_number"),
        "entity_name": customer.get("entity_name"),
        "risk_level": risk_analysis.get("risk_level"),
        "risk_score": risk_analysis.get("risk_score"),
        "risk_indicators": risk_analysis.get("indicators", []),
    }

    # Audit that human approval was requested
    db = SessionLocal()

    try:
        if case_id is not None and not has_audit_event(
            db=db,
            case_id=case_id,
            event_type="HUMAN_APPROVAL_REQUESTED",
        ):
            create_audit_log(
                db=db,
                case_id=case_id,
                event_type="HUMAN_APPROVAL_REQUESTED",
                details=(
                    f"Human approval requested for high-risk case. "
                    f"Risk level: {risk_analysis.get('risk_level')}, "
                    f"risk score: {risk_analysis.get('risk_score')}."
                ),
            )
    finally:
        db.close()
    # Pause workflow and wait for human decision
    decision = interrupt(approval_request)

    if decision == "approve":
        new_status = "APPROVED"
    elif decision == "reject":
        new_status = "REJECTED"
    else:
        return {
            "approval_status": "INVALID",
            "error": (
                "Invalid approval decision. "
                "Expected 'approve' or 'reject'."
            ),
        }

    # Update case status and record the human decision as a single
    # atomic local transaction: either both the status change and its
    # audit event are committed together, or neither is. This
    # transaction is opened and closed entirely within this node, so
    # it is never held open across the interrupt/resume boundary or
    # any LLM call made by later nodes.
    if case_id is not None:
        db = SessionLocal()

        try:
            update_case_status(
                db=db,
                case_id=case_id,
                new_status=new_status,
                commit=False,
            )

            create_audit_log(
                db=db,
                case_id=case_id,
                event_type="HUMAN_APPROVAL",
                details=(
                    f"Human investigator decision: {decision}. "
                    f"Case status changed to {new_status}."
                ),
                commit=False,
            )

            db.commit()

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()

    return {
        "approval_status": decision,
    }