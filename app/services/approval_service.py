from sqlalchemy import update
from sqlalchemy.orm import Session
from langgraph.types import Command

from app.agent.graph import investigation_graph
from app.models.case import InvestigationCase
from app.models.user import User
from app.tools.case_tool import get_case
from app.tools.audit_tool import create_audit_log

PENDING_STATUS = "OPEN"
CLAIMED_STATUS = "UNDER_REVIEW"

DECISION_TO_STATUS = {
    "approve": "APPROVED",
    "reject": "REJECTED",
}


class CaseNotFoundError(Exception):
    pass


class ApprovalNotAllowedError(Exception):
    """Case exists but is not currently eligible for approval/rejection."""


def _revert_claim(db: Session, case_id: int) -> None:
    db.execute(
        update(InvestigationCase)
        .where(InvestigationCase.case_id == case_id)
        .values(status=PENDING_STATUS)
    )
    db.commit()


def apply_approval_decision(
    db: Session,
    case_id: int,
    decision: str,
    actor: User,
) -> dict:
    """
    Resolve case_id -> the server-stored thread_id and resume the
    existing LangGraph HITL interrupt with the given decision.

    The caller (API route) is responsible for authentication and
    role authorization; this function only enforces case-state
    rules and never trusts any client-supplied thread_id.

    TRANSACTION BOUNDARIES
    -----------------------
    This flow spans three separate, independently atomic local
    transactions - a single SQLAlchemy transaction is never held
    open across `investigation_graph.invoke()`, since that call may
    run an LLM call (generate_report_node) and must be free to
    return control back to LangGraph's own checkpointing:

    1. CLAIM (here): one atomic conditional UPDATE
       (OPEN -> UNDER_REVIEW). This is the existing optimistic lock
       that prevents double approval/rejection; it commits on its
       own before the graph is ever resumed.
    2. FINALIZE (inside human_approval_node, app/agent/approval.py):
       the case's terminal status (APPROVED/REJECTED) and its
       primary HUMAN_APPROVAL audit event are written together as
       one atomic transaction there - see that module for details.
       This is the transaction that satisfies "no successful
       case-state change without its audit event" for the decision
       itself.
    3. ACTOR AUDIT (here, after resume returns): a supplementary
       audit entry recording the authenticated actor's identity,
       which the graph/node has no knowledge of. It is written in
       its own atomic commit because the node (step 2) has already
       finalized the case by the time control returns here - there
       is no case-state change left to pair it with.

    If the graph resume itself fails (step 2 never completes), the
    claim from step 1 is rolled back so the case returns to OPEN
    rather than being stuck in UNDER_REVIEW.
    """
    case = get_case(db, case_id)

    if case is None:
        raise CaseNotFoundError()

    if case["risk_level"] != "HIGH":
        raise ApprovalNotAllowedError(
            "This case is not HIGH-risk and does not require approval."
        )

    # Transaction 1: atomically claim the case (OPEN -> UNDER_REVIEW).
    # If another request already claimed or finalized it, rowcount
    # will be 0. This single-statement UPDATE is its own complete
    # transaction; it needs no accompanying audit event because
    # UNDER_REVIEW is a transient lock, not a business outcome.
    claim = db.execute(
        update(InvestigationCase)
        .where(
            InvestigationCase.case_id == case_id,
            InvestigationCase.status == PENDING_STATUS,
        )
        .values(status=CLAIMED_STATUS)
    )
    db.commit()

    if claim.rowcount == 0:
        raise ApprovalNotAllowedError(
            "This case is not currently pending approval."
        )

    thread_id = case.get("thread_id")

    if not thread_id:
        _revert_claim(db, case_id)
        raise ApprovalNotAllowedError(
            "This case has no associated workflow thread to resume."
        )

    config = {"configurable": {"thread_id": thread_id}}

    # Transaction 2 happens here, inside the graph, entirely within
    # human_approval_node's own atomic case-status + audit commit.
    try:
        investigation_graph.invoke(Command(resume=decision), config=config)
    except Exception:
        _revert_claim(db, case_id)
        raise ApprovalNotAllowedError("This case could not be resumed.")

    updated_case = get_case(db, case_id)
    final_status = updated_case["status"] if updated_case else None

    # Transaction 3: a standalone actor-identity audit entry. The
    # existing human_approval_node already committed the case's
    # terminal status together with its own HUMAN_APPROVAL audit
    # event (transaction 2, above) - this call cannot be merged into
    # that transaction because it runs in a different process step,
    # after investigation_graph.invoke() has already returned.
    create_audit_log(
        db=db,
        case_id=case_id,
        event_type="HUMAN_APPROVAL_API",
        details=(
            f"Decision '{decision}' recorded via API for case {case_id} "
            f"by user_id={actor.user_id}, username={actor.username}, "
            f"role={actor.role}. Resulting case status: {final_status}."
        ),
        commit=True,
    )

    return {
        "case_id": case_id,
        "decision": decision,
        "status": final_status,
        "risk_level": case["risk_level"],
        "actor_username": actor.username,
        "actor_role": actor.role,
    }
