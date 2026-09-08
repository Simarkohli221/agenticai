from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt as jose_jwt
from sqlalchemy import select

from app.main import app
from app.db.database import SessionLocal
from app.models.user import User
from app.auth.security import (
    create_access_token,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
)
from scripts.create_test_user import TEST_USERNAME, ensure_test_user
from scripts.test_login import (
    INACTIVE_USERNAME,
    ensure_inactive_test_user,
)


def result_label(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


if __name__ == "__main__":
    db = SessionLocal()

    try:
        valid_password = ensure_test_user(db)
        ensure_inactive_test_user(db)

        active_user = db.execute(
            select(User).where(User.username == TEST_USERNAME)
        ).scalar_one()

        inactive_user = db.execute(
            select(User).where(User.username == INACTIVE_USERNAME)
        ).scalar_one()
    finally:
        db.close()

    client = TestClient(app)

    # Obtain a real JWT through the actual login endpoint.
    login_response = client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": valid_password},
    )
    valid_token = login_response.json().get("access_token")

    # 1. Valid JWT
    response = client.get("/auth/me", headers=auth_header(valid_token))
    body = response.json() if response.status_code == 200 else {}
    valid_jwt_passed = (
        response.status_code == 200
        and body.get("user_id") == active_user.user_id
        and body.get("username") == active_user.username
        and body.get("role") == active_user.role
        and body.get("is_active") is True
    )
    print("Valid JWT:", result_label(valid_jwt_passed))

    # 2. No Authorization header
    response = client.get("/auth/me")
    print("Missing token:", result_label(response.status_code == 401))

    # 3. Malformed token
    response = client.get(
        "/auth/me",
        headers=auth_header("this-is-not-a-valid-jwt"),
    )
    print("Malformed token:", result_label(response.status_code == 401))

    # 4. Invalid signature (signed with a different secret)
    tampered_signature_token = jose_jwt.encode(
        {
            "sub": str(active_user.user_id),
            "username": active_user.username,
            "role": active_user.role,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        "a-different-secret-used-only-for-this-test",
        algorithm=JWT_ALGORITHM,
    )
    response = client.get(
        "/auth/me",
        headers=auth_header(tampered_signature_token),
    )
    print("Invalid signature:", result_label(response.status_code == 401))

    # 5. Expired token (correctly signed, exp in the past)
    expired_token = jose_jwt.encode(
        {
            "sub": str(active_user.user_id),
            "username": active_user.username,
            "role": active_user.role,
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )
    response = client.get("/auth/me", headers=auth_header(expired_token))
    print("Expired token:", result_label(response.status_code == 401))

    # 6. Missing sub claim (correctly signed)
    missing_sub_token = jose_jwt.encode(
        {
            "username": active_user.username,
            "role": active_user.role,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )
    response = client.get("/auth/me", headers=auth_header(missing_sub_token))
    print("Missing sub:", result_label(response.status_code == 401))

    # 7. Non-existent user_id (correctly signed)
    unknown_user_token = jose_jwt.encode(
        {
            "sub": "999999999",
            "username": "ghost_user",
            "role": "INVESTIGATOR",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )
    response = client.get("/auth/me", headers=auth_header(unknown_user_token))
    print("Unknown user:", result_label(response.status_code == 401))

    # 8. Inactive user's otherwise-valid, correctly signed JWT
    inactive_token = create_access_token(
        data={
            "sub": str(inactive_user.user_id),
            "username": inactive_user.username,
            "role": inactive_user.role,
        }
    )
    response = client.get("/auth/me", headers=auth_header(inactive_token))
    print("Inactive user:", result_label(response.status_code == 401))

    # Security check (not an authorization test): a correctly signed token
    # with a tampered role claim must not change the role returned by
    # /auth/me. The database User row is authoritative, not the token body.
    tampered_role_token = create_access_token(
        data={
            "sub": str(active_user.user_id),
            "username": active_user.username,
            "role": "ADMIN",
        }
    )
    response = client.get("/auth/me", headers=auth_header(tampered_role_token))
    db_role_authoritative = (
        response.status_code == 200
        and response.json().get("role") == active_user.role
        and response.json().get("role") != "ADMIN"
    )
    print(
        "Database identity authoritative over token role claim:",
        result_label(db_role_authoritative),
    )
