from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db.database import SessionLocal
from app.models.user import User
from app.auth.security import create_access_token
from app.auth.roles import INVESTIGATOR, SUPERVISOR, ADMIN
from scripts.create_test_user import (
    TEST_USERNAME,
    TEST_SUPERVISOR_USERNAME,
    TEST_ADMIN_USERNAME,
    ensure_test_user,
    ensure_supervisor_test_user,
    ensure_admin_test_user,
)
from scripts.test_login import INACTIVE_USERNAME, ensure_inactive_test_user

ENDPOINTS = {
    "investigator": "/auth/test/investigator",
    "supervisor": "/auth/test/supervisor",
    "admin": "/auth/test/admin",
}


def result_label(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/auth/login",
        json={"username": username, "password": password},
    )
    return response.json().get("access_token")


def check_access(
    client: TestClient,
    token: str,
    endpoint: str,
    expected_status: int,
) -> bool:
    response = client.get(endpoint, headers=auth_header(token))
    return response.status_code == expected_status


if __name__ == "__main__":
    db = SessionLocal()

    try:
        investigator_password = ensure_test_user(db)
        supervisor_password = ensure_supervisor_test_user(db)
        admin_password = ensure_admin_test_user(db)
        ensure_inactive_test_user(db)
    finally:
        db.close()

    client = TestClient(app)

    investigator_token = login(client, TEST_USERNAME, investigator_password)
    supervisor_token = login(client, TEST_SUPERVISOR_USERNAME, supervisor_password)
    admin_token = login(client, TEST_ADMIN_USERNAME, admin_password)

    # 1-3. INVESTIGATOR
    print(
        "Investigator -> investigator:",
        result_label(
            check_access(client, investigator_token, ENDPOINTS["investigator"], 200)
        ),
    )
    print(
        "Investigator -> supervisor:",
        result_label(
            check_access(client, investigator_token, ENDPOINTS["supervisor"], 403)
        ),
    )
    print(
        "Investigator -> admin:",
        result_label(
            check_access(client, investigator_token, ENDPOINTS["admin"], 403)
        ),
    )
    print()

    # 4-6. SUPERVISOR
    print(
        "Supervisor -> investigator:",
        result_label(
            check_access(client, supervisor_token, ENDPOINTS["investigator"], 200)
        ),
    )
    print(
        "Supervisor -> supervisor:",
        result_label(
            check_access(client, supervisor_token, ENDPOINTS["supervisor"], 200)
        ),
    )
    print(
        "Supervisor -> admin:",
        result_label(
            check_access(client, supervisor_token, ENDPOINTS["admin"], 403)
        ),
    )
    print()

    # 7-9. ADMIN
    print(
        "Admin -> investigator:",
        result_label(
            check_access(client, admin_token, ENDPOINTS["investigator"], 200)
        ),
    )
    print(
        "Admin -> supervisor:",
        result_label(
            check_access(client, admin_token, ENDPOINTS["supervisor"], 200)
        ),
    )
    print(
        "Admin -> admin:",
        result_label(check_access(client, admin_token, ENDPOINTS["admin"], 200)),
    )
    print()

    # 10. No JWT
    response = client.get(ENDPOINTS["investigator"])
    print("Missing authentication:", result_label(response.status_code == 401))

    # 11. Inactive user (otherwise-valid, correctly signed token - inactive
    # users cannot obtain a fresh token via /auth/login, so this simulates
    # a token issued before the account was deactivated).
    db = SessionLocal()
    try:
        inactive_user = db.execute(
            select(User).where(User.username == INACTIVE_USERNAME)
        ).scalar_one()
    finally:
        db.close()

    inactive_token = create_access_token(
        data={
            "sub": str(inactive_user.user_id),
            "username": inactive_user.username,
            "role": inactive_user.role,
        }
    )
    response = client.get(
        ENDPOINTS["investigator"],
        headers=auth_header(inactive_token),
    )
    print("Inactive user:", result_label(response.status_code == 401))

    # 12. Authorization must use the live database role, not the JWT role.
    # Reuse the investigator_token obtained BEFORE the role change below.
    db = SessionLocal()
    try:
        investigator_db_user = db.execute(
            select(User).where(User.username == TEST_USERNAME)
        ).scalar_one()
        original_role = investigator_db_user.role
        investigator_db_user.role = SUPERVISOR
        db.commit()
    finally:
        db.close()

    try:
        response = client.get(
            ENDPOINTS["supervisor"],
            headers=auth_header(investigator_token),
        )
        database_role_authority_passed = response.status_code == 200
    finally:
        db = SessionLocal()
        try:
            investigator_db_user = db.execute(
                select(User).where(User.username == TEST_USERNAME)
            ).scalar_one()
            investigator_db_user.role = original_role
            db.commit()
        finally:
            db.close()

    print(
        "Database role authority:",
        result_label(database_role_authority_passed),
    )
