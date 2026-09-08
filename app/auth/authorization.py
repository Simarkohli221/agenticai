"""
Centralized resource-level authorization for investigation cases.

RBAC (require_role, app/auth/dependencies.py) is the outer gate on
every route: it establishes that the caller is authenticated and
holds a role capable of the operation in principle, and it already
returns 401/403 before a route body ever runs.

The functions here are a second, independent check performed by the
service layer itself against the specific case being acted on, so a
sensitive mutation (approve/reject) is never authorized *solely*
because a route dependency happened to run first. This is
defense-in-depth, not a replacement for RBAC.

The current investigation_cases schema has no ownership/assignee
column, so - per the policy this project has defined - any
INVESTIGATOR+ may view any case, and any SUPERVISOR+ may decide any
HIGH-risk case. This module is the single place that policy is
expressed; a future ownership model only has to change these two
functions, not every call site.

Authorization here is deterministic Python over the database User
role - it never consults the LLM, the JWT payload's role claim, or
any client-supplied value.
"""

from sqlalchemy.orm import Session

from app.models.user import User
from app.auth.roles import INVESTIGATOR, SUPERVISOR, ROLE_HIERARCHY
from app.tools.audit_tool import create_audit_log


def can_view_case(user: User, case: dict) -> bool:
    return user.role in ROLE_HIERARCHY[INVESTIGATOR]


def can_approve_case(user: User, case: dict) -> bool:
    return user.role in ROLE_HIERARCHY[SUPERVISOR]


def can_manage_account(user: User) -> bool:
    """
    Governs the controlled account-status action (including, but not
    limited to, freezing). Deliberately the same role set as
    can_approve_case - account status changes are consequential
    banking actions and this project defines no role beyond
    SUPERVISOR/ADMIN for them. Kept as its own named function so the
    policy for account actions can diverge from case-approval policy
    later without touching call sites.
    """
    return user.role in ROLE_HIERARCHY[SUPERVISOR]


def audit_authorization_denied(
    db: Session,
    case_id: int,
    actor: User,
    operation: str,
    reason: str,
) -> None:
    """
    Records a denied sensitive-action attempt. Not used for ordinary
    successful reads - only for a denial that actually reaches this
    resource-level check (see module docstring: RBAC normally denies
    first, so this fires mainly as a defense-in-depth backstop).
    """
    create_audit_log(
        db=db,
        case_id=case_id,
        event_type="AUTHORIZATION_DENIED",
        details=(
            f"Authorization denied for operation '{operation}' on case "
            f"{case_id}. user_id={actor.user_id}, "
            f"username={actor.username}, role={actor.role}. "
            f"Reason: {reason}"
        ),
        commit=True,
    )
