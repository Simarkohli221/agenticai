from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.auth.security import verify_password, create_access_token


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.execute(
        select(User).where(User.username == username)
    ).scalar_one_or_none()


def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> User | None:
    user = get_user_by_username(db, username)

    if user is None:
        return None

    if not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def create_user_access_token(user: User) -> str:
    return create_access_token(
        data={
            "sub": str(user.user_id),
            "username": user.username,
            "role": user.role,
        }
    )
