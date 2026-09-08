from sqlalchemy.orm import Session

from app.models.user import User
from app.tools.account_tool import get_account, update_account_status, ALLOWED_STATUS_TRANSITIONS
from app.tools.case_tool import get_case
from app.tools.audit_tool import create_audit_log
from app.auth.authorization import can_manage_account, audit_authorization_denied

FREEZE_STATUS = "FROZEN"
REQUIRED_FREEZE_RISK_LEVEL = "HIGH"
REQUIRED_FREEZE_CASE_STATUS = "APPROVED"


class AccountNotFoundError(Exception):
    pass


class CaseNotFoundError(Exception):
    pass


class NotAuthorizedError(Exception):
    """Caller is authenticated but not permitted to manage accounts."""


class InvalidTransitionError(Exception):
    """Account/case exist but this status change is not currently allowed."""


def update_account_status_action(
    db: Session,
    account_number: str,
    new_status: str,
    case_id: int,
    actor: User,
) -> dict:
    """
    The single controlled entry point for changing an account's
    status. Never accepts raw SQL or arbitrary fields - only
    account_number, new_status, case_id, and the authenticated actor
    resolved by get_current_user() (never a client-supplied user_id
    or role).

    TRANSACTION BOUNDARIES: this function makes no LangGraph or LLM
    call, so its account-status update and ACCOUNT_STATUS_CHANGED
    audit event are written as one single atomic local transaction
    (same commit=False + explicit db.commit()/db.rollback() pattern
    established in Step 8), with nothing else in between.
    """
    account = get_account(db, account_number)

    if account is None:
        raise AccountNotFoundError()

    case = get_case(db, case_id)

    if case is None:
        raise CaseNotFoundError()

    # Resource-level authorization (defense-in-depth): the route's
    # require_role(SUPERVISOR) dependency already blocks non-eligible
    # roles before this function is ever called. This independently
    # re-verifies using the live database role on `actor` (resolved
    # by get_current_user()), so a future caller of this service that
    # bypasses the route still cannot change account status without
    # satisfying the same policy.
    if not can_manage_account(actor):
        audit_authorization_denied(
            db=db,
            case_id=case_id,
            actor=actor,
            operation="UPDATE_ACCOUNT_STATUS",
            reason="Role is not permitted to manage account status.",
        )
        raise NotAuthorizedError(
            "You are not authorized to update account status."
        )

    if case["account_number"] != account_number:
        raise InvalidTransitionError(
            "The referenced case is not associated with this account."
        )

    current_status = account["status"]
    allowed_next_statuses = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())

    if new_status not in allowed_next_statuses:
        raise InvalidTransitionError(
            f"Cannot transition account from {current_status} to "
            f"{new_status}."
        )

    # Account freezing is consequential: it may only proceed against
    # a case that HITL has already approved as HIGH-risk. The
    # existing case status/risk_level fields are the single source
    # of truth for this - no separate approval flag is introduced.
    if new_status == FREEZE_STATUS:
        if (
            case["risk_level"] != REQUIRED_FREEZE_RISK_LEVEL
            or case["status"] != REQUIRED_FREEZE_CASE_STATUS
        ):
            raise InvalidTransitionError(
                "Freezing an account requires an approved HIGH-risk "
                "investigation case."
            )

    try:
        update_account_status(db, account_number, new_status, commit=False)

        create_audit_log(
            db=db,
            case_id=case_id,
            event_type="ACCOUNT_STATUS_CHANGED",
            details=(
                f"Account {account_number} status changed from "
                f"{current_status} to {new_status} for case {case_id} "
                f"by user_id={actor.user_id}, username={actor.username}, "
                f"role={actor.role}."
            ),
            commit=False,
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "account_number": account_number,
        "previous_status": current_status,
        "new_status": new_status,
        "case_id": case_id,
        "actor_username": actor.username,
        "actor_role": actor.role,
    }
