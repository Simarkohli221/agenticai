import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.user import User
from app.auth.security import hash_password
from app.auth.roles import INVESTIGATOR, SUPERVISOR, ADMIN

# Local development test users only. Do NOT use in production.
TEST_USERNAME = "test_investigator"
TEST_ROLE = INVESTIGATOR
DEFAULT_TEST_PASSWORD = "LocalDevTest#12345"

TEST_SUPERVISOR_USERNAME = "test_supervisor"
DEFAULT_TEST_SUPERVISOR_PASSWORD = "LocalDevTest#Supervisor12345"

TEST_ADMIN_USERNAME = "test_admin"
DEFAULT_TEST_ADMIN_PASSWORD = "LocalDevTest#Admin12345"


def _ensure_user(
    db: Session,
    username: str,
    role: str,
    password: str,
) -> str:
    existing = db.execute(
        select(User).where(User.username == username)
    ).scalar_one_or_none()

    if existing is not None:
        return password

    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )

    db.add(user)
    db.commit()

    return password


def ensure_test_user(db: Session) -> str:
    """
    Ensure the local development INVESTIGATOR test user exists.
    Returns the plaintext password (never stored) so local
    test scripts can exercise the login endpoint without
    hardcoding credentials themselves.
    """
    password = os.getenv("TEST_USER_PASSWORD", DEFAULT_TEST_PASSWORD)
    return _ensure_user(db, TEST_USERNAME, TEST_ROLE, password)


def ensure_supervisor_test_user(db: Session) -> str:
    """
    Ensure the local development SUPERVISOR test user exists.
    Returns the plaintext password (never stored).
    """
    password = os.getenv(
        "TEST_SUPERVISOR_PASSWORD", DEFAULT_TEST_SUPERVISOR_PASSWORD
    )
    return _ensure_user(db, TEST_SUPERVISOR_USERNAME, SUPERVISOR, password)


def ensure_admin_test_user(db: Session) -> str:
    """
    Ensure the local development ADMIN test user exists.
    Returns the plaintext password (never stored).
    """
    password = os.getenv("TEST_ADMIN_PASSWORD", DEFAULT_TEST_ADMIN_PASSWORD)
    return _ensure_user(db, TEST_ADMIN_USERNAME, ADMIN, password)


if __name__ == "__main__":
    db = SessionLocal()

    try:
        for username, role, ensure_fn in (
            (TEST_USERNAME, TEST_ROLE, ensure_test_user),
            (TEST_SUPERVISOR_USERNAME, SUPERVISOR, ensure_supervisor_test_user),
            (TEST_ADMIN_USERNAME, ADMIN, ensure_admin_test_user),
        ):
            existing = db.execute(
                select(User).where(User.username == username)
            ).scalar_one_or_none()

            already_existed = existing is not None

            ensure_fn(db)

            if already_existed:
                print(f"Test user '{username}' already exists. No changes made.")
            else:
                print(f"Created local test user '{username}' with role '{role}'.")

    finally:
        db.close()
