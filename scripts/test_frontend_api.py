"""
Tests the frontend's API-client layer (frontend/api_client.py) in
isolation, using mocked HTTP responses so these tests never depend
on a live backend, a live Streamlit process, or browser automation.

Each mock response mirrors the REAL backend contract as inspected in
app/api/*.py and app/schemas/*.py (see Step 13's report for the
exact endpoints/fields). Where useful, scripts/test_frontend_live.py
(not this file) additionally exercises api_client against a real
running backend - this file is the fast, hermetic layer.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import requests

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
sys.path.insert(0, str(FRONTEND_DIR))

import api_client  # noqa: E402
from api_client import APIError  # noqa: E402


def result_label(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def make_response(status_code: int, json_data=None, has_content=True):
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.content = b"{}" if has_content else b""
    response.json.return_value = json_data if json_data is not None else {}
    return response


if __name__ == "__main__":
    # 1. Login success
    with patch("api_client.requests.request") as mock_request:
        mock_request.return_value = make_response(
            200, {"access_token": "fake.jwt.token", "token_type": "bearer"}
        )
        result = api_client.login("test_investigator", "correct-password")

    test1_passed = (
        result.get("access_token") == "fake.jwt.token"
        and result.get("token_type") == "bearer"
    )
    print("Login success parsed correctly:", result_label(test1_passed))

    # 2. Invalid login -> APIError(401) with a clean message
    with patch("api_client.requests.request") as mock_request:
        mock_request.return_value = make_response(
            401, {"detail": "Incorrect username or password"}
        )
        try:
            api_client.login("test_investigator", "wrong-password")
            test2_passed = False
        except APIError as exc:
            test2_passed = (
                exc.status_code == 401
                and exc.message == "Incorrect username or password"
            )

    print("Invalid login raises a clean 401 error:", result_label(test2_passed))

    # 3. Authenticated user retrieval
    with patch("api_client.requests.request") as mock_request:
        mock_request.return_value = make_response(
            200,
            {
                "user_id": 1,
                "username": "test_investigator",
                "role": "INVESTIGATOR",
                "is_active": True,
            },
        )
        user = api_client.get_current_user("fake.jwt.token")

    test3_passed = (
        user.get("username") == "test_investigator"
        and user.get("role") == "INVESTIGATOR"
        and user.get("is_active") is True
    )
    print("Authenticated user retrieval parsed correctly:", result_label(test3_passed))

    if test3_passed:
        request_kwargs = mock_request.call_args
        sent_headers = request_kwargs.kwargs.get("headers", {})
        auth_header_sent = sent_headers.get("Authorization") == "Bearer fake.jwt.token"
    else:
        auth_header_sent = False
    print("Bearer token is attached to the request:", result_label(auth_header_sent))

    # 4. Investigation request (arbitrary account number, not hardcoded)
    with patch("api_client.requests.request") as mock_request:
        mock_request.return_value = make_response(
            200,
            {
                "case_id": 42,
                "account_number": "SOME-OTHER-ACCT-9",
                "risk_level": "LOW",
                "risk_score": 10,
                "approval_required": False,
                "approval_status": None,
                "investigation_report": {
                    "account": "SOME-OTHER-ACCT-9",
                    "risk_level": "LOW",
                    "policy_evidence_found": True,
                    "policy_evidence": [
                        {"policy": "aml_policy.txt", "chunk_id": 2, "excerpt": "..."}
                    ],
                    "policy_citations": ["aml_policy.txt (chunk 2)"],
                    "llm_summary": "Summary text.",
                },
                "customer": {"account_number": "SOME-OTHER-ACCT-9"},
                "transactions": [],
                "message": None,
            },
        )
        result = api_client.create_investigation(
            "fake.jwt.token", "Investigate account SOME-OTHER-ACCT-9."
        )
        sent_body = mock_request.call_args.kwargs.get("json")

    test4_passed = (
        result.get("account_number") == "SOME-OTHER-ACCT-9"
        and sent_body == {"user_request": "Investigate account SOME-OTHER-ACCT-9."}
    )
    print(
        "Investigation request sent and parsed for an arbitrary account:",
        result_label(test4_passed),
    )

    # 5. Investigation result parsing (structural check of nested fields)
    report = result.get("investigation_report", {})
    test5_passed = (
        result.get("case_id") == 42
        and report.get("policy_evidence_found") is True
        and len(report.get("policy_evidence", [])) == 1
        and report["policy_evidence"][0]["policy"] == "aml_policy.txt"
    )
    print("Nested investigation report fields parsed correctly:", result_label(test5_passed))

    # 6. Unauthorized request handling (403)
    with patch("api_client.requests.request") as mock_request:
        mock_request.return_value = make_response(
            403, {"detail": "Insufficient permissions"}
        )
        try:
            api_client.submit_approval("fake.jwt.token", 42, "approve")
            test6_passed = False
        except APIError as exc:
            test6_passed = exc.status_code == 403 and "Insufficient" in exc.message

    print("Unauthorized (403) request handled cleanly:", result_label(test6_passed))

    # 7. Supervisor approval request
    with patch("api_client.requests.request") as mock_request:
        mock_request.return_value = make_response(
            200,
            {
                "case_id": 99,
                "decision": "approve",
                "status": "APPROVED",
                "risk_level": "HIGH",
                "actor_username": "test_supervisor",
                "actor_role": "SUPERVISOR",
            },
        )
        outcome = api_client.submit_approval("fake.jwt.token", 99, "approve")
        sent_body = mock_request.call_args.kwargs.get("json")
        sent_path = mock_request.call_args.args[1] if len(mock_request.call_args.args) > 1 else mock_request.call_args.kwargs.get("url")

    test7_passed = (
        outcome.get("status") == "APPROVED"
        and sent_body == {"decision": "approve"}
    )
    print("Supervisor approval request sent and parsed:", result_label(test7_passed))

    # 8. Rejected approval
    with patch("api_client.requests.request") as mock_request:
        mock_request.return_value = make_response(
            200,
            {
                "case_id": 100,
                "decision": "reject",
                "status": "REJECTED",
                "risk_level": "HIGH",
                "actor_username": "test_supervisor",
                "actor_role": "SUPERVISOR",
            },
        )
        outcome = api_client.submit_approval("fake.jwt.token", 100, "reject")

    test8_passed = outcome.get("status") == "REJECTED" and outcome.get("decision") == "reject"
    print("Rejection request sent and parsed:", result_label(test8_passed))

    # 9. Controlled account status request
    with patch("api_client.requests.request") as mock_request:
        mock_request.return_value = make_response(
            200,
            {
                "account_number": "SOME-OTHER-ACCT-9",
                "previous_status": "ACTIVE",
                "new_status": "REVIEW",
                "case_id": 42,
                "actor_username": "test_supervisor",
                "actor_role": "SUPERVISOR",
            },
        )
        outcome = api_client.update_account_status(
            "fake.jwt.token", "SOME-OTHER-ACCT-9", "REVIEW", 42
        )
        sent_body = mock_request.call_args.kwargs.get("json")

    test9_passed = (
        outcome.get("new_status") == "REVIEW"
        and sent_body == {"new_status": "REVIEW", "case_id": 42}
    )
    print("Controlled account status request sent and parsed:", result_label(test9_passed))

    # 10. Backend unavailable handling (connection error / timeout)
    with patch("api_client.requests.request") as mock_request:
        mock_request.side_effect = requests.exceptions.ConnectionError()
        try:
            api_client.login("someone", "something")
            test10a_passed = False
        except APIError as exc:
            test10a_passed = exc.status_code is None and "reach the backend" in exc.message

    with patch("api_client.requests.request") as mock_request:
        mock_request.side_effect = requests.exceptions.Timeout()
        try:
            api_client.login("someone", "something")
            test10b_passed = False
        except APIError as exc:
            test10b_passed = exc.status_code is None and "too long" in exc.message

    test10_passed = test10a_passed and test10b_passed
    print("Backend-unavailable/timeout handled cleanly:", result_label(test10_passed))

    # Extra: 409 and 422 mapping, and 500 never leaks internals
    with patch("api_client.requests.request") as mock_request:
        mock_request.return_value = make_response(
            409, {"detail": "This case is not currently pending approval."}
        )
        try:
            api_client.submit_approval("fake.jwt.token", 42, "approve")
            conflict_passed = False
        except APIError as exc:
            conflict_passed = exc.status_code == 409

    with patch("api_client.requests.request") as mock_request:
        mock_request.return_value = make_response(
            422,
            {
                "detail": [
                    {"loc": ["body", "decision"], "msg": "Input should be 'approve' or 'reject'"}
                ]
            },
        )
        try:
            api_client.submit_approval("fake.jwt.token", 42, "maybe")
            validation_passed = False
        except APIError as exc:
            validation_passed = exc.status_code == 422 and "decision" in exc.message

    with patch("api_client.requests.request") as mock_request:
        mock_request.return_value = make_response(500, {"detail": "Traceback (most recent call last)..."})
        try:
            api_client.get_case("fake.jwt.token", 1)
            server_error_passed = False
        except APIError as exc:
            server_error_passed = (
                exc.status_code == 500
                and "Traceback" not in exc.message
            )

    extra_passed = conflict_passed and validation_passed and server_error_passed
    print(
        "409/422 mapped correctly and 500 never leaks internals:",
        result_label(extra_passed),
    )
