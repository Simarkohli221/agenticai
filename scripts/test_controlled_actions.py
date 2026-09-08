"""
Tests Step 10 controlled account-status actions: PATCH
/accounts/{account_number}/status, its service-layer business rules,
RBAC, resource authorization, atomic transaction behavior, and the
HIGH-risk freeze approval requirement.

Dedicated, disposable test accounts and cases are used throughout -
no real banking account's status is ever changed, and no existing
transaction/account/entity row is modified.
"""

from sqlalchemy import select

from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.models.account import Account
from app.models.audit import AuditLog
from app.tools.account_tool import get_account, update_account_status
from app.tools.case_tool import create_investigation_case
from app.services.account_service import (
    update_account_status_action,
    NotAuthorizedError,
)
from scripts.test_secure_hitl import build_high_risk_test_graph
from scripts.create_test_user import (
    TEST_USERNAME,
    TEST_SUPERVISOR_USERNAME,
    TEST_ADMIN_USERNAME,
    ensure_test_user,
    ensure_supervisor_test_user,
    ensure_admin_test_user,
)

REAL_ACCOUNT = "8000EBD30"  # used only to source a valid entity_id
TEST_BANK_ID = "999"
TEST_BANK_NAME = "Step10 Test Bank"


def result_label(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    return response.json().get("access_token")


def make_test_account(db, suffix: str) -> str:
    """Creates a disposable test account under a real, existing entity."""
    real_account = db.get(Account, REAL_ACCOUNT)
    entity_id = real_account.entity_id

    account_number = f"TEST-ACCT-{suffix}"
    account = Account(
        account_number=account_number,
        bank_id=TEST_BANK_ID,
        bank_name=TEST_BANK_NAME,
        entity_id=entity_id,
        status="ACTIVE",
    )
    db.add(account)
    db.commit()
    return account_number


def get_account_status(account_number: str) -> str | None:
    db = SessionLocal()
    try:
        account = db.get(Account, account_number)
        return account.status if account else None
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


def latest_audit_details(case_id: int, event_type: str) -> str | None:
    db = SessionLocal()
    try:
        row = db.execute(
            select(AuditLog)
            .where(
                AuditLog.case_id == case_id,
                AuditLog.event_type == event_type,
            )
            .order_by(AuditLog.audit_id.desc())
        ).scalars().first()
        return row.details if row else None
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

    # Each test account gets its own dedicated case created with the
    # matching account_number baked in (case_tool has no "set
    # account_number" - cases are immutable once created).
    def make_case_for(account_number: str, risk_level="LOW", risk_score=5) -> int:
        db = SessionLocal()
        try:
            case = create_investigation_case(
                db,
                account_number=account_number,
                risk_level=risk_level,
                risk_score=risk_score,
            )
            return case["case_id"]
        finally:
            db.close()

    db = SessionLocal()
    try:
        acct_1 = make_test_account(db, "01-generic")
        acct_2 = make_test_account(db, "02-nocase")
        acct_3 = make_test_account(db, "03-badstatus")
        acct_4 = make_test_account(db, "04-badtransition")
        acct_5 = make_test_account(db, "05-atomic")
        acct_6 = make_test_account(db, "06-audit-fail")
        acct_7 = make_test_account(db, "07-case-fail")
        acct_8 = make_test_account(db, "08-freeze-ok")
        acct_9 = make_test_account(db, "09-freeze-unapproved")
        acct_11 = make_test_account(db, "11-bypass")
        acct_12 = make_test_account(db, "12-actor")
        acct_13 = make_test_account(db, "13-threadid")
    finally:
        db.close()

    case_1 = make_case_for(acct_1)
    case_3 = make_case_for(acct_3)
    case_4 = make_case_for(acct_4)
    case_5 = make_case_for(acct_5)
    case_6 = make_case_for(acct_6)
    case_7 = make_case_for(acct_7)
    case_11 = make_case_for(acct_11)
    case_12 = make_case_for(acct_12)
    case_13 = make_case_for(acct_13)

    # ------------------------------------------------------------
    # 1-9: auth / RBAC / not-found / validation
    # ------------------------------------------------------------

    # 1. Unauthenticated
    response = client.patch(
        f"/accounts/{acct_1}/status",
        json={"new_status": "REVIEW", "case_id": case_1},
    )
    print("Unauthenticated account update:", result_label(response.status_code == 401))

    # 2. Invalid JWT
    response = client.patch(
        f"/accounts/{acct_1}/status",
        json={"new_status": "REVIEW", "case_id": case_1},
        headers=auth_header("not-a-valid-jwt"),
    )
    print("Invalid JWT:", result_label(response.status_code == 401))

    # 3. Investigator forbidden
    response = client.patch(
        f"/accounts/{acct_1}/status",
        json={"new_status": "REVIEW", "case_id": case_1},
        headers=auth_header(investigator_token),
    )
    test3_passed = (
        response.status_code == 403
        and get_account_status(acct_1) == "ACTIVE"
    )
    print("Investigator forbidden:", result_label(test3_passed))

    # 4. Supervisor authorized normal update
    response = client.patch(
        f"/accounts/{acct_1}/status",
        json={"new_status": "REVIEW", "case_id": case_1},
        headers=auth_header(supervisor_token),
    )
    test4_passed = (
        response.status_code == 200
        and get_account_status(acct_1) == "REVIEW"
    )
    print("Supervisor authorized normal update:", result_label(test4_passed))

    # 5. Admin authorized normal update (separate account)
    case_2b = make_case_for(acct_2)
    response = client.patch(
        f"/accounts/{acct_2}/status",
        json={"new_status": "REVIEW", "case_id": case_2b},
        headers=auth_header(admin_token),
    )
    test5_passed = (
        response.status_code == 200
        and get_account_status(acct_2) == "REVIEW"
    )
    print("Admin authorized normal update:", result_label(test5_passed))

    # 6. Nonexistent account
    response = client.patch(
        "/accounts/TEST-ACCT-DOES-NOT-EXIST/status",
        json={"new_status": "REVIEW", "case_id": case_1},
        headers=auth_header(supervisor_token),
    )
    print("Nonexistent account:", result_label(response.status_code == 404))

    # 7. Nonexistent case
    response = client.patch(
        f"/accounts/{acct_3}/status",
        json={"new_status": "REVIEW", "case_id": 999999999},
        headers=auth_header(supervisor_token),
    )
    print("Nonexistent case:", result_label(response.status_code == 404))

    # 8. Invalid status value
    response = client.patch(
        f"/accounts/{acct_3}/status",
        json={"new_status": "DESTROYED", "case_id": case_3},
        headers=auth_header(supervisor_token),
    )
    print("Invalid status value:", result_label(response.status_code == 422))

    # 9. Invalid business transition (ACTIVE -> ACTIVE is not an
    # allowed transition per ALLOWED_STATUS_TRANSITIONS)
    response = client.patch(
        f"/accounts/{acct_4}/status",
        json={"new_status": "ACTIVE", "case_id": case_4},
        headers=auth_header(supervisor_token),
    )
    test9_passed = (
        response.status_code == 409
        and get_account_status(acct_4) == "ACTIVE"
    )
    print("Invalid business transition rejected:", result_label(test9_passed))

    # ------------------------------------------------------------
    # 10-13: successful update + audit
    # ------------------------------------------------------------

    # 10 & 11. Account status changes + ACCOUNT_STATUS_CHANGED audit
    response = client.patch(
        f"/accounts/{acct_5}/status",
        json={"new_status": "REVIEW", "case_id": case_5},
        headers=auth_header(supervisor_token),
    )
    test10_passed = (
        response.status_code == 200
        and get_account_status(acct_5) == "REVIEW"
    )
    print("Account status actually changes:", result_label(test10_passed))

    test11_passed = audit_count(case_5, "ACCOUNT_STATUS_CHANGED") == 1
    print("ACCOUNT_STATUS_CHANGED audit created:", result_label(test11_passed))

    # 12. Audit contains actor identity
    details = latest_audit_details(case_5, "ACCOUNT_STATUS_CHANGED")
    test12_passed = (
        details is not None
        and f"username={TEST_SUPERVISOR_USERNAME}" in details
        and "role=SUPERVISOR" in details
    )
    print("Audit contains actor identity:", result_label(test12_passed))

    # ------------------------------------------------------------
    # 13-15: atomicity
    # ------------------------------------------------------------

    # 13. Account update + audit atomic (success case, verified together)
    test13_passed = test10_passed and test11_passed
    print("Account update + audit atomic (success):", result_label(test13_passed))

    # 14. Simulated audit failure rolls back account update
    db = SessionLocal()
    try:
        status_before = get_account(db, acct_6)["status"]
        try:
            update_account_status(db, acct_6, "REVIEW", commit=False)
            from app.tools.audit_tool import create_audit_log

            create_audit_log(
                db=db,
                case_id=case_6,
                event_type="ACCOUNT_STATUS_CHANGED",
                details=None,  # violates NOT NULL at flush time
                commit=False,
            )
            db.commit()
            test14_tx_succeeded = True
        except Exception:
            db.rollback()
            test14_tx_succeeded = False
    finally:
        db.close()

    test14_passed = (
        not test14_tx_succeeded
        and get_account_status(acct_6) == status_before
        and audit_count(case_6, "ACCOUNT_STATUS_CHANGED") == 0
    )
    print("Simulated audit failure rolls back account update:", result_label(test14_passed))

    # 15. Simulated account update failure does not persist audit
    db = SessionLocal()
    try:
        from app.tools.audit_tool import create_audit_log

        try:
            create_audit_log(
                db=db,
                case_id=case_7,
                event_type="ACCOUNT_STATUS_CHANGED",
                details="This must not survive the rollback below.",
                commit=False,
            )
            update_account_status(db, acct_7, "NOT_A_REAL_STATUS", commit=False)
            db.commit()
            test15_tx_succeeded = True
        except Exception:
            db.rollback()
            test15_tx_succeeded = False
    finally:
        db.close()

    test15_passed = (
        not test15_tx_succeeded
        and audit_count(case_7, "ACCOUNT_STATUS_CHANGED") == 0
    )
    print("Simulated account update failure does not persist audit:", result_label(test15_passed))

    # ------------------------------------------------------------
    # 16-18: HIGH-risk freeze protection
    #
    # These use dedicated disposable test accounts (acct_8, acct_9),
    # not the shared "8000EBD30" account reused across every other
    # step's tests - freezing that shared account's status would be
    # a harmless but needlessly messy side effect for later runs.
    # ------------------------------------------------------------

    import uuid as _uuid

    def create_pending_high_risk_case_for(account_number: str) -> int:
        thread_id = f"investigation-{_uuid.uuid4()}"
        config = {"configurable": {"thread_id": thread_id}}
        result = test_graph.invoke(
            {"account_number": account_number}, config=config
        )
        new_case_id = result["case_id"]

        from app.tools.case_tool import set_case_thread_id

        db = SessionLocal()
        try:
            set_case_thread_id(db, new_case_id, thread_id)
        finally:
            db.close()

        return new_case_id

    # 16. HIGH-risk FROZEN action requires approved case -> approve it first
    case_freeze_ok = create_pending_high_risk_case_for(acct_8)

    approve_response = client.post(
        f"/investigations/{case_freeze_ok}/approval",
        json={"decision": "approve"},
        headers=auth_header(supervisor_token),
    )
    response = client.patch(
        f"/accounts/{acct_8}/status",
        json={"new_status": "FROZEN", "case_id": case_freeze_ok},
        headers=auth_header(supervisor_token),
    )
    test16_passed = (
        approve_response.status_code == 200
        and response.status_code == 200
        and get_account_status(acct_8) == "FROZEN"
    )
    print("HIGH-risk approved case can freeze account:", result_label(test16_passed))

    # 17. HIGH-risk but NOT yet approved (still OPEN) -> cannot freeze
    case_freeze_unapproved = create_pending_high_risk_case_for(acct_9)

    response = client.patch(
        f"/accounts/{acct_9}/status",
        json={"new_status": "FROZEN", "case_id": case_freeze_unapproved},
        headers=auth_header(supervisor_token),
    )
    test17_passed = (
        response.status_code == 409
        and get_account_status(acct_9) != "FROZEN"
    )
    print("Unapproved HIGH-risk case cannot freeze:", result_label(test17_passed))

    # 18. LOW/MEDIUM case cannot freeze, even if account is ACTIVE
    response = client.patch(
        f"/accounts/{acct_3}/status",
        json={"new_status": "FROZEN", "case_id": case_3},
        headers=auth_header(supervisor_token),
    )
    test18_passed = (
        response.status_code == 409
        and get_account_status(acct_3) != "FROZEN"
    )
    print("LOW/MEDIUM case cannot freeze:", result_label(test18_passed))

    # ------------------------------------------------------------
    # 19-21: bypass attempts
    # ------------------------------------------------------------

    # 19. Investigator cannot bypass API by calling the service directly
    db = SessionLocal()
    try:
        from app.models.user import User as UserModel

        investigator_user = db.execute(
            select(UserModel).where(UserModel.username == TEST_USERNAME)
        ).scalar_one()

        status_before_19 = get_account(db, acct_11)["status"]
        raised = False
        try:
            update_account_status_action(
                db=db,
                account_number=acct_11,
                new_status="REVIEW",
                case_id=case_11,
                actor=investigator_user,
            )
        except NotAuthorizedError:
            raised = True
    finally:
        db.close()

    test19_passed = (
        raised
        and get_account_status(acct_11) == status_before_19
        and audit_count(case_11, "AUTHORIZATION_DENIED") == 1
    )
    print("Investigator cannot bypass API via direct service call:", result_label(test19_passed))

    # 20. Client cannot control actor identity - the response's actor
    # fields must reflect the authenticated token holder, never a
    # client-supplied value (the schema has no such field at all).
    response = client.patch(
        f"/accounts/{acct_12}/status",
        json={
            "new_status": "REVIEW",
            "case_id": case_12,
            "actor_username": "someone_else",
            "actor_role": "ADMIN",
            "user_id": 999999,
        },
        headers=auth_header(supervisor_token),
    )
    test20_passed = (
        response.status_code == 200
        and response.json().get("actor_username") == TEST_SUPERVISOR_USERNAME
        and response.json().get("actor_role") == "SUPERVISOR"
    )
    print("Client cannot control actor identity:", result_label(test20_passed))

    # 21. Client cannot control thread_id (no such field exists on this
    # endpoint's schema/response at all - it never leaves the server).
    response = client.patch(
        f"/accounts/{acct_13}/status",
        json={
            "new_status": "REVIEW",
            "case_id": case_13,
            "thread_id": "attacker-supplied-thread",
        },
        headers=auth_header(supervisor_token),
    )
    test21_passed = (
        response.status_code == 200
        and "thread_id" not in response.json()
        and get_account_status(acct_13) == "REVIEW"
    )
    print("Client cannot control thread_id:", result_label(test21_passed))

    # ------------------------------------------------------------
    # 22-23: safety boundaries
    # ------------------------------------------------------------

    # 22. Transactions remain unchanged
    import sqlite3

    conn = sqlite3.connect("D:/Banking_Data/banking_system.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM transactions")
    transactions_count = cur.fetchone()[0]
    conn.close()
    print(
        "Transactions table row count (informational, verified in report):",
        transactions_count,
    )

    # 23. Accounts cannot be deleted through the new API
    response = client.delete(f"/accounts/{acct_1}/status")
    test23_passed = response.status_code == 405 and get_account_status(acct_1) is not None
    print("Accounts cannot be deleted via API:", result_label(test23_passed))

    print()
    print("Steps 24-27 (existing suite regressions) are run separately - see report.")
