from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.auth.security import decode_access_token
from app.auth.roles import ROLE_HIERARCHY

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        raise _unauthorized()

    raw_user_id = payload.get("sub")

    if raw_user_id is None:
        raise _unauthorized()

    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError):
        raise _unauthorized()

    user = db.get(User, user_id)

    if user is None:
        raise _unauthorized()

    if not user.is_active:
        raise _unauthorized()

    return user


def require_role(required_role: str) -> Callable[[User], User]:
    """
    Returns a FastAPI dependency that authorizes the current user
    against `required_role` using ROLE_HIERARCHY. Authorization is
    always evaluated against the live database User returned by
    get_current_user() - never against the JWT payload directly.
    """
    allowed_roles = ROLE_HIERARCHY.get(required_role, {required_role})

    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return current_user

    return role_checker
