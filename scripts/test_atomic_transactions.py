"""
Tests the Step 8 atomic case-state + audit transaction behavior.

Items 1-6 exercise the tool-layer transaction primitives directly
against a dedicated, disposable test case (no LangGraph, no LLM
calls). Items 2-3 exercise a real approval/rejection through the
actual FastAPI endpoints, reusing the Step 7 controlled
force_high_risk test-case harness (zero LLM calls to create the
pending cases; one LLM call per resume, same as Step 7). Items 7-10
are regression checks that re-run the existing test suites from
prior steps as subprocesses.
"""

import subprocess
import sys

from sqlalchemy import select

from app.db.database import SessionLocal
from app.tools.case_tool import (
    create_investigation_case,
    get_case,
    update_case_status,
)
from app.tools.audit_tool import create_audit_log, has_audit_event
from app.models.audit import AuditLog
from scripts.test_secure_hitl import (
    build_high_risk_test_graph,
    create_pending_high_risk_case,
)
from scripts.create_test_user import (
    TEST_SUPERVISOR_USERNAME,
    TEST_ADMIN_USERNAME,
    ensure_supervisor_test_user,
    ensure_admin_test_user,
)
from fastapi.testclient import TestClient
from app.main import app

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


def audit_count_for_event(db, case_id: int, event_type: str) -> int:
    return len(
        db.execute(
            select(AuditLog.audit_id).where(
                AuditLog.case_id == case_id,
                AuditLog.event_type == event_type,
            )
        ).all()
    )


def run_regression_module(module: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", module],
        capture_output=True,
        text=True,
    )
    output = proc.stdout + proc.stderr
    passed = proc.returncode == 0 and "FAIL" not in output
    return passed, output


if __name__ == "__main__":
    # ------------------------------------------------------------
    # Items 1, 4, 5, 6: direct tool-layer transaction tests, using
    # one dedicated, disposable test case created purely at the DB
    # level (no LangGraph involved).
    # ------------------------------------------------------------
    db = SessionLocal()
    try:
        test_case = create_investigation_case(
            db,
            account_number=TEST_ACCOUNT,
            risk_level="HIGH",
            risk_score=80,
        )
        test_case_id = test_case["case_id"]
    finally:
        db.close()

    # 1. Successful case update + audit -> both exist after commit.
    db = SessionLocal()
    try:
        update_case_status(db, test_case_id, "UNDER_REVIEW", commit=False)
        create_audit_log(
            db=db,
            case_id=test_case_id,
            event_type="TEST_ATOMIC_SUCCESS",
            details="Successful atomic case update + audit test.",
            commit=False,
        )
        db.commit()
    finally:
        db.close()

    db = SessionLocal()
    try:
        case_after = get_case(db, test_case_id)
        audit_exists = has_audit_event(db, test_case_id, "TEST_ATOMIC_SUCCESS")
    finally:
        db.close()

    test1_passed = case_after["status"] == "UNDER_REVIEW" and audit_exists
    print("Successful case update + audit:", result_label(test1_passed))

    # 4, 5, 6 share ONE session on purpose, to prove rollback leaves
    # the session usable for a subsequent successful transaction.
    db = SessionLocal()

    # 4. Simulated audit failure -> case update rolls back.
    status_before_test4 = get_case(db, test_case_id)["status"]
    try:
        update_case_status(db, test_case_id, "APPROVED", commit=False)
        create_audit_log(
            db=db,
            case_id=test_case_id,
            event_type="TEST_ATOMIC_AUDIT_FAILURE",
            details=None,  # violates the NOT NULL constraint at flush time
            commit=False,
        )
        db.commit()
        test4_transaction_succeeded = True
    except Exception:
        db.rollback()
        test4_transaction_succeeded = False

    case_after_test4 = get_case(db, test_case_id)
    audit4_exists = has_audit_event(
        db, test_case_id, "TEST_ATOMIC_AUDIT_FAILURE"
    )
    test4_passed = (
        not test4_transaction_succeeded
        and case_after_test4["status"] == status_before_test4
        and not audit4_exists
    )
    print("Simulated audit failure rolls back case update:", result_label(test4_passed))

    # 5. Simulated case-update failure -> audit not partially persisted.
    status_before_test5 = get_case(db, test_case_id)["status"]
    try:
        create_audit_log(
            db=db,
            case_id=test_case_id,
            event_type="TEST_ATOMIC_CASE_FAILURE",
            details="This audit event must not survive the rollback below.",
            commit=False,
        )
        update_case_status(
            db, test_case_id, "NOT_A_REAL_STATUS", commit=False
        )  # raises ValueError before touching the DB
        db.commit()
        test5_transaction_succeeded = True
    except Exception:
        db.rollback()
        test5_transaction_succeeded = False

    case_after_test5 = get_case(db, test_case_id)
    audit5_exists = has_audit_event(
        db, test_case_id, "TEST_ATOMIC_CASE_FAILURE"
    )
    test5_passed = (
        not test5_transaction_succeeded
        and case_after_test5["status"] == status_before_test5
        and not audit5_exists
    )
    print(
        "Simulated case update failure rolls back audit insert:",
        result_label(test5_passed),
    )

    # 6. Successful transaction after rollback -> the same session,
    # already rolled back twice above, still works correctly.
    try:
        update_case_status(db, test_case_id, "CLOSED", commit=False)
        create_audit_log(
            db=db,
            case_id=test_case_id,
            event_type="TEST_ATOMIC_RECOVERY",
            details="Session remains usable after prior rollbacks.",
            commit=False,
        )
        db.commit()
        test6_committed = True
    except Exception:
        db.rollback()
        test6_committed = False

    case_after_test6 = get_case(db, test_case_id)
    audit6_exists = has_audit_event(db, test_case_id, "TEST_ATOMIC_RECOVERY")
    test6_passed = (
        test6_committed
        and case_after_test6["status"] == "CLOSED"
        and audit6_exists
    )
    print(
        "Successful transaction after rollback:",
        result_label(test6_passed),
    )

    db.close()

    # ------------------------------------------------------------
    # Items 2, 3: real approval/rejection through the actual API,
    # verifying the atomic case+audit pair in human_approval_node.
    # ------------------------------------------------------------
    setup_db = SessionLocal()
    try:
        supervisor_password = ensure_supervisor_test_user(setup_db)
        admin_password = ensure_admin_test_user(setup_db)
    finally:
        setup_db.close()

    client = TestClient(app)
    supervisor_token = login(client, TEST_SUPERVISOR_USERNAME, supervisor_password)
    admin_token = login(client, TEST_ADMIN_USERNAME, admin_password)

    test_graph = build_high_risk_test_graph()
    approve_case_id, _ = create_pending_high_risk_case(test_graph)
    reject_case_id, _ = create_pending_high_risk_case(test_graph)

    response = client.post(
        f"/investigations/{approve_case_id}/approval",
        json={"decision": "approve"},
        headers=auth_header(supervisor_token),
    )
    db = SessionLocal()
    try:
        approved_case = get_case(db, approve_case_id)
        approved_case_has_actor_audit = audit_count_for_event(
            db, approve_case_id, "HUMAN_APPROVAL_API"
        ) == 1
        approved_case_has_decision_audit = audit_count_for_event(
            db, approve_case_id, "HUMAN_APPROVAL"
        ) == 1
    finally:
        db.close()

    test2_passed = (
        response.status_code == 200
        and approved_case["status"] == "APPROVED"
        and approved_case_has_actor_audit
        and approved_case_has_decision_audit
    )
    print("Successful approval + actor audit:", result_label(test2_passed))

    response = client.post(
        f"/investigations/{reject_case_id}/approval",
        json={"decision": "reject"},
        headers=auth_header(admin_token),
    )
    db = SessionLocal()
    try:
        rejected_case = get_case(db, reject_case_id)
        rejected_case_has_actor_audit = audit_count_for_event(
            db, reject_case_id, "HUMAN_APPROVAL_API"
        ) == 1
        rejected_case_has_decision_audit = audit_count_for_event(
            db, reject_case_id, "HUMAN_APPROVAL"
        ) == 1
    finally:
        db.close()

    test3_passed = (
        response.status_code == 200
        and rejected_case["status"] == "REJECTED"
        and rejected_case_has_actor_audit
        and rejected_case_has_decision_audit
    )
    print("Successful rejection + actor audit:", result_label(test3_passed))

    # ------------------------------------------------------------
    # Items 7-10: regression - re-run the existing suites unchanged.
    # ------------------------------------------------------------
    for label, module in (
        ("Existing HITL tests (double-approval + full suite)", "scripts.test_secure_hitl"),
        ("Existing investigation API tests", "scripts.test_investigation_api"),
        ("Existing login tests", "scripts.test_login"),
        ("Existing current-user tests", "scripts.test_current_user"),
        ("Existing RBAC tests", "scripts.test_rbac"),
    ):
        passed, _output = run_regression_module(module)
        print(f"{label}:", result_label(passed))
