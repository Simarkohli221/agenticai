from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.models.case import InvestigationCase
from scripts.create_test_user import (
    TEST_USERNAME,
    TEST_SUPERVISOR_USERNAME,
    TEST_ADMIN_USERNAME,
    ensure_test_user,
    ensure_supervisor_test_user,
    ensure_admin_test_user,
)

# Known-good account used throughout the existing test scripts/data.
KNOWN_ACCOUNT_REQUEST = (
    "Investigate account 8000EBD30 for suspicious activity."
)
# Account number that does not exist in the database.
UNKNOWN_ACCOUNT_REQUEST = (
    "Investigate account ZZZZ00000000NOPE for suspicious activity."
)


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


def count_cases() -> int:
    db = SessionLocal()
    try:
        return db.query(InvestigationCase).count()
    finally:
        db.close()


if __name__ == "__main__":
    db = SessionLocal()
    try:
        investigator_password = ensure_test_user(db)
        supervisor_password = ensure_supervisor_test_user(db)
        admin_password = ensure_admin_test_user(db)
    finally:
        db.close()

    client = TestClient(app)

    investigator_token = login(client, TEST_USERNAME, investigator_password)
    supervisor_token = login(client, TEST_SUPERVISOR_USERNAME, supervisor_password)
    admin_token = login(client, TEST_ADMIN_USERNAME, admin_password)

    cases_before_auth_tests = count_cases()

    # 1. No JWT
    response = client.post(
        "/investigations", json={"user_request": KNOWN_ACCOUNT_REQUEST}
    )
    print("No JWT:", result_label(response.status_code == 401))

    # 2. Invalid JWT
    response = client.post(
        "/investigations",
        json={"user_request": KNOWN_ACCOUNT_REQUEST},
        headers=auth_header("not-a-valid-jwt"),
    )
    print("Invalid JWT:", result_label(response.status_code == 401))

    no_business_logic_reached = count_cases() == cases_before_auth_tests
    print(
        "Unauthenticated requests did not reach business logic:",
        result_label(no_business_logic_reached),
    )

    # 6. Invalid request body (missing required field) - checked early,
    # before spending any LLM calls, since Pydantic rejects it up front.
    response = client.post(
        "/investigations",
        json={},
        headers=auth_header(investigator_token),
    )
    print("Invalid request body:", result_label(response.status_code == 422))

    # 3. Investigator JWT - the single controlled, full success-path call.
    response = client.post(
        "/investigations",
        json={"user_request": KNOWN_ACCOUNT_REQUEST},
        headers=auth_header(investigator_token),
    )
    investigator_allowed = response.status_code == 200
    print("Investigator JWT allowed:", result_label(investigator_allowed))

    known_case_id = response.json().get("case_id") if investigator_allowed else None

    # 4. Supervisor JWT - allowed check via the cheap nonexistent-account
    # path (still passes RBAC, avoids a second full report generation).
    response = client.post(
        "/investigations",
        json={"user_request": UNKNOWN_ACCOUNT_REQUEST},
        headers=auth_header(supervisor_token),
    )
    print(
        "Supervisor JWT allowed:",
        result_label(response.status_code not in (401, 403)),
    )

    # 7. Valid authenticated request for a nonexistent account
    #    -> controlled error, no traceback (reusing the call above).
    controlled_error = (
        response.status_code == 404
        and "detail" in response.json()
        and "Traceback" not in response.text
    )
    print("Nonexistent account handled safely:", result_label(controlled_error))

    # 5. Admin JWT - allowed check via the same cheap nonexistent-account path.
    response = client.post(
        "/investigations",
        json={"user_request": UNKNOWN_ACCOUNT_REQUEST},
        headers=auth_header(admin_token),
    )
    print(
        "Admin JWT allowed:",
        result_label(response.status_code not in (401, 403)),
    )

    # 10. No JWT for case retrieval
    response = client.get(f"/investigations/{known_case_id}")
    print("Case retrieval - no JWT:", result_label(response.status_code == 401))

    # 8 / 11. Existing case retrieval - investigator
    response = client.get(
        f"/investigations/{known_case_id}",
        headers=auth_header(investigator_token),
    )
    print(
        "Case retrieval - investigator (known case):",
        result_label(response.status_code == 200),
    )

    # 12. Existing case retrieval - supervisor
    response = client.get(
        f"/investigations/{known_case_id}",
        headers=auth_header(supervisor_token),
    )
    print(
        "Case retrieval - supervisor (known case):",
        result_label(response.status_code == 200),
    )

    # 13. Existing case retrieval - admin
    response = client.get(
        f"/investigations/{known_case_id}",
        headers=auth_header(admin_token),
    )
    print(
        "Case retrieval - admin (known case):",
        result_label(response.status_code == 200),
    )

    # 9. Nonexistent case
    response = client.get(
        "/investigations/999999999",
        headers=auth_header(investigator_token),
    )
    print(
        "Case retrieval - nonexistent case:",
        result_label(response.status_code == 404),
    )
