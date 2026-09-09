"""
HTTP client for the Banking Transaction Investigation Agent's FastAPI
backend. This module is the ONLY place the frontend talks to the
backend - it never touches the database, SQLAlchemy, or any secret
(JWT signing key, Groq API key, etc.). It only ever sends the Bearer
token the backend already issued via POST /auth/login.

Every function here maps 1:1 to a real, already-existing backend
endpoint (see app/api/*.py). No endpoint paths or response fields are
guessed - see the docstring on each function for the exact backend
route/schema it calls.
"""

import os

import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
REQUEST_TIMEOUT_SECONDS = 20


class APIError(Exception):
    """
    Raised for any non-2xx response or transport failure. `message`
    is always safe to show directly to the user - it never includes
    a stack trace or internal exception text.
    """

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _extract_detail(response: requests.Response) -> str | None:
    try:
        data = response.json()
    except ValueError:
        return None

    if not isinstance(data, dict):
        return None

    detail = data.get("detail")

    if isinstance(detail, str):
        return detail

    # FastAPI/Pydantic's automatic 422 validation-error shape: a list
    # of {"loc": [...], "msg": "...", ...} objects.
    if isinstance(detail, list):
        messages = []

        for item in detail:
            if isinstance(item, dict) and "msg" in item:
                location = ".".join(
                    str(part) for part in item.get("loc", []) if part != "body"
                )
                messages.append(f"{location}: {item['msg']}" if location else item["msg"])

        if messages:
            return "; ".join(messages)

    return None


_STATUS_FALLBACK_MESSAGES = {
    400: "The request was invalid.",
    401: "Your session has expired or is invalid. Please log in again.",
    403: "You do not have permission to perform this action.",
    404: "The requested resource was not found.",
    409: "This action cannot be completed in the case's/account's current state.",
    422: "The request was invalid.",
}


def _request(
    method: str,
    path: str,
    token: str | None = None,
    json_body: dict | None = None,
) -> dict:
    url = f"{API_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            json=json_body,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.ConnectionError:
        raise APIError(
            "Could not reach the backend. Make sure the FastAPI "
            f"server is running at {API_BASE_URL}."
        )
    except requests.exceptions.Timeout:
        raise APIError("The backend took too long to respond. Please try again.")
    except requests.exceptions.RequestException:
        raise APIError("Could not complete the request to the backend.")

    if 200 <= response.status_code < 300:
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            raise APIError("The backend returned an unreadable response.")

    detail = _extract_detail(response)
    fallback = _STATUS_FALLBACK_MESSAGES.get(
        response.status_code,
        f"The backend returned an unexpected error (status {response.status_code}).",
    )

    if response.status_code >= 500:
        # Never surface backend internals for server errors.
        message = "The backend encountered an internal error. Please try again later."
    else:
        message = detail or fallback

    raise APIError(message, status_code=response.status_code)


# ---------------------------------------------------------------------------
# POST /auth/login -> TokenResponse {access_token, token_type}
# ---------------------------------------------------------------------------
def login(username: str, password: str) -> dict:
    return _request(
        "POST",
        "/auth/login",
        json_body={"username": username, "password": password},
    )


# ---------------------------------------------------------------------------
# GET /auth/me -> CurrentUserResponse {user_id, username, role, is_active}
# ---------------------------------------------------------------------------
def get_current_user(token: str) -> dict:
    return _request("GET", "/auth/me", token=token)


# ---------------------------------------------------------------------------
# POST /investigations -> InvestigationResponse
# ---------------------------------------------------------------------------
def create_investigation(token: str, user_request: str) -> dict:
    return _request(
        "POST",
        "/investigations",
        token=token,
        json_body={"user_request": user_request},
    )


# ---------------------------------------------------------------------------
# GET /investigations/{case_id} -> CaseResponse
# ---------------------------------------------------------------------------
def get_case(token: str, case_id: int) -> dict:
    return _request("GET", f"/investigations/{case_id}", token=token)


# ---------------------------------------------------------------------------
# POST /investigations/{case_id}/approval -> ApprovalResponse
# ---------------------------------------------------------------------------
def submit_approval(token: str, case_id: int, decision: str) -> dict:
    return _request(
        "POST",
        f"/investigations/{case_id}/approval",
        token=token,
        json_body={"decision": decision},
    )


# ---------------------------------------------------------------------------
# PATCH /accounts/{account_number}/status -> AccountStatusUpdateResponse
# ---------------------------------------------------------------------------
def update_account_status(
    token: str,
    account_number: str,
    new_status: str,
    case_id: int,
) -> dict:
    return _request(
        "PATCH",
        f"/accounts/{account_number}/status",
        token=token,
        json_body={"new_status": new_status, "case_id": case_id},
    )
