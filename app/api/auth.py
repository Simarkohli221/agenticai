from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.auth.dependencies import get_current_user, require_role
from app.auth.roles import INVESTIGATOR, SUPERVISOR, ADMIN
from app.schemas.auth import LoginRequest, TokenResponse, CurrentUserResponse
from app.services.auth_service import authenticate_user, create_user_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = authenticate_user(db, payload.username, payload.password)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token = create_user_access_token(user)

    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(
    current_user: User = Depends(get_current_user),
) -> CurrentUserResponse:
    return CurrentUserResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        role=current_user.role,
        is_active=current_user.is_active,
    )


# The following endpoints exist only to prove the RBAC mechanism
# (require_role) works end-to-end. They are not business endpoints.


@router.get("/test/investigator")
def test_investigator_access(
    current_user: User = Depends(require_role(INVESTIGATOR)),
) -> dict:
    return {"message": "investigator access granted"}


@router.get("/test/supervisor")
def test_supervisor_access(
    current_user: User = Depends(require_role(SUPERVISOR)),
) -> dict:
    return {"message": "supervisor access granted"}


@router.get("/test/admin")
def test_admin_access(
    current_user: User = Depends(require_role(ADMIN)),
) -> dict:
    return {"message": "admin access granted"}
