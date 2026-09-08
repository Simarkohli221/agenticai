from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.auth.dependencies import require_role
from app.auth.roles import SUPERVISOR
from app.schemas.account import AccountStatusUpdateRequest, AccountStatusUpdateResponse
from app.services.account_service import (
    update_account_status_action,
    AccountNotFoundError,
    CaseNotFoundError,
    NotAuthorizedError,
    InvalidTransitionError,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.patch("/{account_number}/status", response_model=AccountStatusUpdateResponse)
def update_account_status_endpoint(
    account_number: str,
    payload: AccountStatusUpdateRequest,
    current_user: User = Depends(require_role(SUPERVISOR)),
    db: Session = Depends(get_db),
) -> AccountStatusUpdateResponse:
    try:
        outcome = update_account_status_action(
            db=db,
            account_number=account_number,
            new_status=payload.new_status,
            case_id=payload.case_id,
            actor=current_user,
        )
    except AccountNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found.",
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
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return AccountStatusUpdateResponse(**outcome)
