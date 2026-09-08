from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db.database import SessionLocal
from app.models.user import User
from app.auth.security import hash_password, decode_access_token
from scripts.create_test_user import TEST_USERNAME, TEST_ROLE, ensure_test_user

# Local development test user only. Do NOT use in production.
INACTIVE_USERNAME = "test_inactive_investigator"
INACTIVE_PASSWORD = "LocalDevInactive#12345"


def ensure_inactive_test_user(db) -> None:
    existing = db.execute(
        select(User).where(User.username == INACTIVE_USERNAME)
    ).scalar_one_or_none()

    if existing is not None:
        return

    user = User(
        username=INACTIVE_USERNAME,
        password_hash=hash_password(INACTIVE_PASSWORD),
        role=TEST_ROLE,
        is_active=False,
    )

    db.add(user)
    db.commit()


def result_label(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


if __name__ == "__main__":
    db = SessionLocal()

    try:
        valid_password = ensure_test_user(db)
        ensure_inactive_test_user(db)
    finally:
        db.close()

    client = TestClient(app)

    # 1. Valid username + valid password
    response = client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": valid_password},
    )
    body = response.json() if response.status_code == 200 else {}
    valid_login_passed = (
        response.status_code == 200
        and "access_token" in body
        and body.get("token_type") == "bearer"
    )
    print("Valid login:", result_label(valid_login_passed))

    access_token = body.get("access_token")

    # 2. Invalid password
    response = client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": "clearly-wrong-password"},
    )
    print(
        "Invalid password:",
        result_label(response.status_code == 401),
    )

    # 3. Invalid username
    response = client.post(
        "/auth/login",
        json={"username": "nonexistent_user_xyz", "password": "irrelevant"},
    )
    print(
        "Invalid username:",
        result_label(response.status_code == 401),
    )

    # 4. Inactive user
    response = client.post(
        "/auth/login",
        json={"username": INACTIVE_USERNAME, "password": INACTIVE_PASSWORD},
    )
    print(
        "Inactive user:",
        result_label(response.status_code == 401),
    )

    # 5. Decode and validate the JWT issued for the valid login
    if access_token:
        try:
            claims = decode_access_token(access_token)
            signature_ok = True
        except Exception:
            claims = {}
            signature_ok = False

        claims_ok = (
            signature_ok
            and "sub" in claims
            and "username" in claims
            and "role" in claims
            and "password" not in claims
            and "password_hash" not in claims
        )
        expiry_ok = signature_ok and "exp" in claims
    else:
        signature_ok = False
        claims_ok = False
        expiry_ok = False

    print("JWT signature:", result_label(signature_ok))
    print("JWT claims:", result_label(claims_ok))
    print("JWT expiry:", result_label(expiry_ok))
