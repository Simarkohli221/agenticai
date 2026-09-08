"""
Tests the secured HITL approval/rejection API (Step 7) against the
real FastAPI endpoints and the real, running investigation_graph.

Dedicated HIGH-risk pending test cases are created using the
project's existing controlled `force_high_risk_node` test pattern
(the same mechanism scripts/test_high_risk.py already uses), so no
change to the real risk engine is needed and no real suspicious
banking data is required. Each such test graph is compiled with a
checkpointer pointed at the SAME LangGraph checkpoint database file
used by the real app.agent.graph.investigation_graph, so the actual
API (which resumes via that real graph object) can resume the
threads created here.
"""

import sqlite3
import uuid

from fastapi.testclient import TestClient
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from sqlalchemy import select

from app.main import app
from app.db.database import SessionLocal
from app.models.case import InvestigationCase
from app.agent.state import InvestigationState
from app.agent.nodes import (
    create_case_node,
    get_customer_node,
    get_transactions_node,
    search_policy_node,
    generate_report_node,
)
from app.agent.approval import human_approval_node
from app.agent.test_nodes import force_high_risk_node
from app.agent.routing import route_by_risk
from app.tools.case_tool import set_case_thread_id
from app.tools.audit_tool import create_audit_log
from scripts.create_test_user import (
    TEST_USERNAME,
    TEST_SUPERVISOR_USERNAME,
    TEST_ADMIN_USERNAME,
    ensure_test_user,
    ensure_supervisor_test_user,
    ensure_admin_test_user,
)

# Must match app/agent/graph.py exactly - the real API resumes
# threads via the real investigation_graph, which is bound to this
# checkpoint file.
CHECKPOINT_DB_PATH = "D:/Banking_Data/langgraph_checkpoints.db"

TEST_ACCOUNT = "8000EBD30"


def build_high_risk_test_graph():
    connection = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(connection)
    checkpointer.setup()

    graph = StateGraph(InvestigationState)
    graph.add_node("get_customer", get_customer_node)
    graph.add_node("get_transactions", get_transactions_node)
    graph.add_node("search_policy", search_policy_node)
    graph.add_node("force_high_risk", force_high_risk_node)
    graph.add_node("create_case", create_case_node)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("generate_report", generate_report_node)

    graph.add_edge(START, "get_customer")
    graph.add_edge("get_customer", "get_transactions")
    graph.add_edge("get_transactions", "search_policy")
    graph.add_edge("search_policy", "force_high_risk")
    graph.add_edge("force_high_risk", "create_case")
    graph.add_conditional_edges(
        "create_case",
        route_by_risk,
        {"low_risk": "generate_report", "high_risk": "human_approval"},
    )
    graph.add_edge("human_approval", "generate_report")
    graph.add_edge("generate_report", END)

    return graph.compile(checkpointer=checkpointer)


def create_pending_high_risk_case(test_graph) -> tuple[int, str]:
    """
    Creates one dedicated HIGH-risk case left in a pending-approval
    state (status OPEN, thread_id persisted), ready to be resumed by
    the real API. Uses zero LLM calls.
    """
    thread_id = f"investigation-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}

    result = test_graph.invoke({"account_number": TEST_ACCOUNT}, config=config)
    case_id = result["case_id"]

    db = SessionLocal()
    try:
        set_case_thread_id(db, case_id, thread_id)
    finally:
        db.close()

    return case_id, thread_id


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


def get_existing_non_high_case_id() -> int:
    db = SessionLocal()
    try:
        case = db.execute(
            select(InvestigationCase)
            .where(InvestigationCase.risk_level != "HIGH")
            .limit(1)
        ).scalar_one()
        return case.case_id
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

    case_a, thread_a = create_pending_high_risk_case(test_graph)
    case_b, thread_b = create_pending_high_risk_case(test_graph)
    case_c, thread_c = create_pending_high_risk_case(test_graph)
    case_d, thread_d = create_pending_high_risk_case(test_graph)

    low_risk_case_id = get_existing_non_high_case_id()

    # 1. Investigator attempts approval
    response = client.post(
        f"/investigations/{case_a}/approval",
        json={"decision": "approve"},
        headers=auth_header(investigator_token),
    )
    print("Investigator approval forbidden:", result_label(response.status_code == 403))

    # 2. Investigator attempts rejection
    response = client.post(
        f"/investigations/{case_a}/approval",
        json={"decision": "reject"},
        headers=auth_header(investigator_token),
    )
    print("Investigator rejection forbidden:", result_label(response.status_code == 403))

    # 3. Supervisor approves case A
    response = client.post(
        f"/investigations/{case_a}/approval",
        json={"decision": "approve"},
        headers=auth_header(supervisor_token),
    )
    supervisor_approve_ok = (
        response.status_code == 200
        and get_case_status(case_a) == "APPROVED"
    )
    print("Supervisor approves pending case:", result_label(supervisor_approve_ok))

    # 4. Supervisor attempts to approve the same case again
    response = client.post(
        f"/investigations/{case_a}/approval",
        json={"decision": "approve"},
        headers=auth_header(supervisor_token),
    )
    print("Double approval rejected:", result_label(response.status_code == 409))

    # 5. Supervisor attempts to reject the already-approved case
    response = client.post(
        f"/investigations/{case_a}/approval",
        json={"decision": "reject"},
        headers=auth_header(supervisor_token),
    )
    print(
        "Reject-after-approve rejected:",
        result_label(response.status_code == 409),
    )

    # 6. Admin approves case B
    response = client.post(
        f"/investigations/{case_b}/approval",
        json={"decision": "approve"},
        headers=auth_header(admin_token),
    )
    admin_approve_ok = (
        response.status_code == 200
        and get_case_status(case_b) == "APPROVED"
    )
    print("Admin approves separate pending case:", result_label(admin_approve_ok))

    # 7. Admin rejects case C
    response = client.post(
        f"/investigations/{case_c}/approval",
        json={"decision": "reject"},
        headers=auth_header(admin_token),
    )
    admin_reject_ok = (
        response.status_code == 200
        and get_case_status(case_c) == "REJECTED"
    )
    print("Admin rejects separate pending case:", result_label(admin_reject_ok))

    # 8. Approval of LOW/MEDIUM-risk case
    response = client.post(
        f"/investigations/{low_risk_case_id}/approval",
        json={"decision": "approve"},
        headers=auth_header(supervisor_token),
    )
    print(
        "Approval of non-HIGH-risk case rejected:",
        result_label(response.status_code == 409),
    )

    # 9. Rejection of LOW/MEDIUM-risk case
    response = client.post(
        f"/investigations/{low_risk_case_id}/approval",
        json={"decision": "reject"},
        headers=auth_header(supervisor_token),
    )
    print(
        "Rejection of non-HIGH-risk case rejected:",
        result_label(response.status_code == 409),
    )

    # 10. Nonexistent case
    response = client.post(
        "/investigations/999999999/approval",
        json={"decision": "approve"},
        headers=auth_header(supervisor_token),
    )
    print("Nonexistent case:", result_label(response.status_code == 404))

    # 11. Missing JWT
    response = client.post(
        f"/investigations/{case_d}/approval",
        json={"decision": "approve"},
    )
    print("Missing JWT:", result_label(response.status_code == 401))

    # 12. Invalid JWT
    response = client.post(
        f"/investigations/{case_d}/approval",
        json={"decision": "approve"},
        headers=auth_header("not-a-valid-jwt"),
    )
    print("Invalid JWT:", result_label(response.status_code == 401))

    # 13. Invalid decision value
    response = client.post(
        f"/investigations/{case_d}/approval",
        json={"decision": "maybe"},
        headers=auth_header(supervisor_token),
    )
    print("Invalid decision value:", result_label(response.status_code == 422))

    # 14. Client attempts to supply a thread_id (another case's real one,
    # to actively try to hijack it) - it must have no effect.
    response = client.post(
        f"/investigations/{case_d}/approval",
        json={"decision": "approve", "thread_id": thread_a},
        headers=auth_header(supervisor_token),
    )
    hijack_attempt_had_no_effect = (
        response.status_code == 200
        and get_case_status(case_d) == "APPROVED"
        # case A must remain exactly as test 3 left it - untouched by
        # this second call despite supplying case A's real thread_id.
        and get_case_status(case_a) == "APPROVED"
    )
    print(
        "Client-supplied thread_id ignored:",
        result_label(hijack_attempt_had_no_effect),
    )

    # 15 / 16. Audit log records the actor identity and decision.
    db = SessionLocal()
    try:
        from app.models.audit import AuditLog

        audit_rows = db.execute(
            select(AuditLog)
            .where(
                AuditLog.case_id == case_d,
                AuditLog.event_type == "HUMAN_APPROVAL_API",
            )
        ).scalars().all()
    finally:
        db.close()

    audit_exists = len(audit_rows) == 1
    audit_has_actor = audit_exists and (
        f"username={TEST_SUPERVISOR_USERNAME}" in audit_rows[0].details
        and "role=SUPERVISOR" in audit_rows[0].details
        and "'approve'" in audit_rows[0].details
    )
    print("Audit log recorded:", result_label(audit_exists))
    print("Audit log contains actor identity and decision:", result_label(audit_has_actor))
