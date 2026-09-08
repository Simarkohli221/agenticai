from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.auth.dependencies import require_role
from app.auth.roles import INVESTIGATOR, SUPERVISOR
from app.auth.authorization import can_view_case, audit_authorization_denied
from app.schemas.investigation import (
    InvestigationRequest,
    InvestigationResponse,
    CaseResponse,
    ApprovalRequest,
    ApprovalResponse,
)
from app.services.investigation_service import run_investigation
from app.services.approval_service import (
    apply_approval_decision,
    CaseNotFoundError,
    ApprovalNotAllowedError,
    NotAuthorizedError,
)
from app.tools.case_tool import get_case

router = APIRouter(prefix="/investigations", tags=["investigations"])


@router.post("", response_model=InvestigationResponse)
def create_investigation(
    payload: InvestigationRequest,
    current_user: User = Depends(require_role(INVESTIGATOR)),
    db: Session = Depends(get_db),
) -> InvestigationResponse:
    result = run_investigation(db, payload.user_request, current_user)

    report = result.get("investigation_report")

    if report and report.get("status") == "ERROR":
        message = report.get(
            "message", "Investigation could not be completed."
        )

        if "not found" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message,
            )

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=message,
        )

    interrupted = "__interrupt__" in result

    return InvestigationResponse(
        case_id=result.get("case_id"),
        account_number=result.get("account_number"),
        risk_level=result.get("risk_level"),
        risk_score=result.get("risk_analysis", {}).get("risk_score"),
        approval_required=bool(result.get("approval_required", False)),
        approval_status=result.get("approval_status"),
        investigation_report=result.get("investigation_report"),
        message=(
            "High-risk investigation requires human approval before a "
            "report can be generated."
            if interrupted
            else None
        ),
    )


@router.get("/{case_id}", response_model=CaseResponse)
def read_investigation_case(
    case_id: int,
    current_user: User = Depends(require_role(INVESTIGATOR)),
    db: Session = Depends(get_db),
) -> CaseResponse:
    case = get_case(db, case_id)

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found.",
        )

    # Resource-level authorization, applied after existing RBAC and
    # after confirming the case exists. Under the current policy any
    # INVESTIGATOR+ may view any case (no ownership column exists on
    # investigation_cases), so this is normally a pass-through - but
    # it is the single, centralized place that decision is made, so
    # no route can bypass it.
    if not can_view_case(current_user, case):
        audit_authorization_denied(
            db=db,
            case_id=case_id,
            actor=current_user,
            operation="VIEW_CASE",
            reason="Role is not permitted to view this case.",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this case.",
        )

    return CaseResponse(**case)


@router.post("/{case_id}/approval", response_model=ApprovalResponse)
def decide_investigation_case(
    case_id: int,
    payload: ApprovalRequest,
    current_user: User = Depends(require_role(SUPERVISOR)),
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    try:
        outcome = apply_approval_decision(
            db=db,
            case_id=case_id,
            decision=payload.decision,
            actor=current_user,
        )
    except CaseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found.",
        )
    except NotAuthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    except ApprovalNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return ApprovalResponse(**outcome)
