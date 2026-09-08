"""
Tests Step 9 resource-level authorization: the centralized
can_view_case()/can_approve_case() checks in app/auth/authorization.py,
wired into GET /investigations/{case_id} and the approval service.

Dedicated HIGH-risk pending cases are created with the existing
Step 7 force_high_risk test harness (zero LLM calls). Test 15/16
call the approval service directly (bypassing the route's RBAC
dependency entirely) to genuinely exercise the internal
defense-in-depth authorization check, since going through the real
HTTP route would never reach it (require_role already blocks first).
"""

from sqlalchemy import select

from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.models.case import InvestigationCase
from app.models.audit import AuditLog
from app.tools.case_tool import create_investigation_case, get_case
from app.services.approval_service import apply_approval_decision, NotAuthorizedError
from scripts.test_secure_hitl import (
    build_high_risk_test_graph,
    create_pending_high_risk_case,
)
from scripts.create_test_user import (
    TEST_USERNAME,
    TEST_SUPERVISOR_USERNAME,
    TEST_ADMIN_USERNAME,
    ensure_test_user,
    ensure_supervisor_test_user,
    ensure_admin_test_user,
)

TEST_ACCOUNT = "8000EBD30"


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


def get_case_status(case_id: int) -> str | None:
    db = SessionLocal()
    try:
        case = db.execute(
            select(InvestigationCase).where(InvestigationCase.case_id == case_id)
        ).scalar_one_or_none()
        return case.status if case else None
    finally:
        db.close()


def get_user_by_username(db, username: str):
    from app.models.user import User

    return db.execute(
        select(User).where(User.username == username)
    ).scalar_one()


def set_user_role(username: str, role: str) -> None:
    db = SessionLocal()
    try:
        user = get_user_by_username(db, username)
        user.role = role
        db.commit()
    finally:
        db.close()


def audit_count(case_id: int, event_type: str) -> int:
    db = SessionLocal()
    try:
        return len(
            db.execute(
                select(AuditLog.audit_id).where(
                    AuditLog.case_id == case_id,
                    AuditLog.event_type == event_type,
                )
            ).all()
        )
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

    test_graph = build_high_risk_test_graph()

    # A plain, non-HIGH case used only for the view tests (1-6).
    db = SessionLocal()
    try:
        view_case = create_investigation_case(
            db, account_number=TEST_ACCOUNT, risk_level="LOW", risk_score=10
        )
        view_case_id = view_case["case_id"]
    finally:
        db.close()

    # 1. Unauthenticated case retrieval
    response = client.get(f"/investigations/{view_case_id}")
    print("Unauthenticated case retrieval:", result_label(response.status_code == 401))

    # 2. Invalid JWT
    response = client.get(
        f"/investigations/{view_case_id}", headers=auth_header("not-a-valid-jwt")
    )
    print("Invalid JWT case retrieval:", result_label(response.status_code == 401))

    # 3. Investigator can retrieve
    response = client.get(
        f"/investigations/{view_case_id}", headers=auth_header(investigator_token)
    )
    print("Investigator can retrieve case:", result_label(response.status_code == 200))

    # 4. Supervisor can retrieve
    response = client.get(
        f"/investigations/{view_case_id}", headers=auth_header(supervisor_token)
    )
    print("Supervisor can retrieve case:", result_label(response.status_code == 200))

    # 5. Admin can retrieve
    response = client.get(
        f"/investigations/{view_case_id}", headers=auth_header(admin_token)
    )
    print("Admin can retrieve case:", result_label(response.status_code == 200))

    # 6. Nonexistent case
    response = client.get(
        "/investigations/999999999", headers=auth_header(investigator_token)
    )
    print("Nonexistent case retrieval:", result_label(response.status_code == 404))

    # Dedicated pending HIGH-risk cases for the approval tests.
    case_x, _ = create_pending_high_risk_case(test_graph)  # 7 -> 8 -> 11
    case_y, _ = create_pending_high_risk_case(test_graph)  # 9
    case_z, _ = create_pending_high_risk_case(test_graph)  # 12
    case_v, thread_v = create_pending_high_risk_case(test_graph)  # 13 (target)
    case_w, _ = create_pending_high_risk_case(test_graph)  # 13 (hijack victim)

    db = SessionLocal()
    try:
        non_high_case = create_investigation_case(
            db,
            account_number=TEST_ACCOUNT,
            risk_level="MEDIUM",
            risk_score=35,
        )
        non_high_case_id = non_high_case["case_id"]
    finally:
        db.close()

    # 7. Investigator cannot approve (case must remain pending)
    response = client.post(
        f"/investigations/{case_x}/approval",
        json={"decision": "approve"},
        headers=auth_header(investigator_token),
    )
    test7_passed = (
        response.status_code == 403 and get_case_status(case_x) == "OPEN"
    )
    print("Investigator cannot approve:", result_label(test7_passed))

    # 8. Supervisor can approve the (still pending) eligible case
    response = client.post(
        f"/investigations/{case_x}/approval",
        json={"decision": "approve"},
        headers=auth_header(supervisor_token),
    )
    test8_passed = (
        response.status_code == 200 and get_case_status(case_x) == "APPROVED"
    )
    print("Supervisor can approve eligible case:", result_label(test8_passed))

    # 9. Admin can approve a separate eligible case
    response = client.post(
        f"/investigations/{case_y}/approval",
        json={"decision": "approve"},
        headers=auth_header(admin_token),
    )
    test9_passed = (
        response.status_code == 200 and get_case_status(case_y) == "APPROVED"
    )
    print("Admin can approve eligible case:", result_label(test9_passed))

    # 10. Non-HIGH case approval -> existing 409 behavior
    response = client.post(
        f"/investigations/{non_high_case_id}/approval",
        json={"decision": "approve"},
        headers=auth_header(supervisor_token),
    )
    print("Non-HIGH case approval rejected:", result_label(response.status_code == 409))

    # 11. Already-approved case -> conflict
    response = client.post(
        f"/investigations/{case_x}/approval",
        json={"decision": "approve"},
        headers=auth_header(supervisor_token),
    )
    print("Already-approved case rejected:", result_label(response.status_code == 409))

    # 12. Already-rejected case -> conflict
    client.post(
        f"/investigations/{case_z}/approval",
        json={"decision": "reject"},
        headers=auth_header(admin_token),
    )
    response = client.post(
        f"/investigations/{case_z}/approval",
        json={"decision": "reject"},
        headers=auth_header(admin_token),
    )
    test12_passed = (
        response.status_code == 409 and get_case_status(case_z) == "REJECTED"
    )
    print("Already-rejected case rejected:", result_label(test12_passed))

    # 13. Client-supplied thread_id cannot influence which thread resumes
    response = client.post(
        f"/investigations/{case_v}/approval",
        json={"decision": "approve", "thread_id": "hijack-attempt-value"},
        headers=auth_header(supervisor_token),
    )
    # thread_v itself is never sent by the client - fetch case_w's real
    # thread and try it too, targeting a DIFFERENT case than it belongs to.
    db = SessionLocal()
    try:
        case_w_thread = get_case(db, case_w)["thread_id"]
    finally:
        db.close()
    response2 = client.post(
        f"/investigations/{case_v}/approval",
        json={"decision": "approve", "thread_id": case_w_thread},
        headers=auth_header(supervisor_token),
    )
    test13_passed = (
        response.status_code == 200
        and get_case_status(case_v) == "APPROVED"
        and get_case_status(case_w) == "OPEN"  # untouched by the hijack attempt
    )
    print("Client-supplied thread_id ignored:", result_label(test13_passed))

    # 14. DB role change after token issuance still governs authorization
    # for this endpoint chain (require_role + can_approve_case together).
    case_role_test, _ = create_pending_high_risk_case(test_graph)
    response = client.post(
        f"/investigations/{case_role_test}/approval",
        json={"decision": "approve"},
        headers=auth_header(investigator_token),
    )
    denied_as_investigator = response.status_code == 403

    set_user_role(TEST_USERNAME, "SUPERVISOR")
    try:
        response = client.post(
            f"/investigations/{case_role_test}/approval",
            json={"decision": "approve"},
            headers=auth_header(investigator_token),  # same old token
        )
        allowed_after_db_role_change = (
            response.status_code == 200
            and get_case_status(case_role_test) == "APPROVED"
        )
    finally:
        set_user_role(TEST_USERNAME, "INVESTIGATOR")

    test14_passed = denied_as_investigator and allowed_after_db_role_change
    print("DB role change governs authorization:", result_label(test14_passed))

    # 15 / 16. Direct service-level test of the internal defense-in-depth
    # check - bypasses the route's require_role entirely, since the real
    # HTTP route would always block an investigator before this code runs.
    case_defense, _ = create_pending_high_risk_case(test_graph)

    db = SessionLocal()
    try:
        investigator_user = get_user_by_username(db, TEST_USERNAME)
        raised = False
        try:
            apply_approval_decision(
                db=db,
                case_id=case_defense,
                decision="approve",
                actor=investigator_user,
            )
        except NotAuthorizedError:
            raised = True
    finally:
        db.close()

    status_after_denial = get_case_status(case_defense)
    denial_audit_count = audit_count(case_defense, "AUTHORIZATION_DENIED")
    approval_audit_count = audit_count(case_defense, "HUMAN_APPROVAL")

    test15_passed = raised and status_after_denial == "OPEN"
    test16_passed = denial_audit_count == 1 and approval_audit_count == 0

    print("Authorization denial does not mutate case status:", result_label(test15_passed))
    print(
        "Authorization denial creates only the denial audit (no case mutation):",
        result_label(test16_passed),
    )
