"""
Streamlit frontend for the Banking Transaction Investigation Agent.

This app is purely an API client for the existing FastAPI backend
(see app/main.py, app/api/*.py). It never touches the database, never
imports SQLAlchemy or any backend model, and never makes an
authorization decision itself - every business rule (RBAC, resource
authorization, risk routing, HITL, account-action validation) is
enforced by the backend and only ever displayed here.

The JWT issued by POST /auth/login is kept only in
st.session_state - never written to disk, never logged.
"""

import streamlit as st

import api_client
from api_client import APIError
import ui

st.set_page_config(
    page_title="Banking Investigation Agent",
    page_icon="🏦",
    layout="wide",
)


def init_session_state() -> None:
    st.session_state.setdefault("token", None)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("last_investigation", None)
    st.session_state.setdefault("last_case_lookup", None)


def do_logout() -> None:
    st.session_state["token"] = None
    st.session_state["user"] = None
    st.session_state["last_investigation"] = None
    st.session_state["last_case_lookup"] = None
    st.rerun()


def handle_api_error(exc: APIError) -> None:
    if exc.status_code == 401:
        st.session_state["token"] = None
        st.session_state["user"] = None
        st.session_state["last_investigation"] = None
        st.session_state["last_case_lookup"] = None
        st.error("Your session has expired or is invalid. Please log in again.")
        st.rerun()
    else:
        st.error(exc.message)


def render_login() -> None:
    st.title("🏦 Banking Transaction Investigation Agent")
    st.caption("Sign in with your investigator, supervisor, or admin account.")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", type="primary")

    if not submitted:
        return

    if not username or not password:
        st.warning("Please enter both a username and password.")
        return

    try:
        token_response = api_client.login(username, password)
    except APIError as exc:
        st.error(exc.message)
        return

    token = token_response.get("access_token")
    if not token:
        st.error("Login succeeded but no access token was returned.")
        return

    try:
        user = api_client.get_current_user(token)
    except APIError as exc:
        st.error(f"Logged in, but could not load your profile: {exc.message}")
        return

    if not user.get("is_active", True):
        st.error("This account is inactive. Contact an administrator.")
        return

    st.session_state["token"] = token
    st.session_state["user"] = user
    st.rerun()


def render_investigator_dashboard(token: str) -> None:
    st.header("Run an Investigation")
    st.caption(
        "Enter a natural-language investigation request for any valid "
        "account number. Examples (for illustration only - any account "
        "number is supported):\n\n"
        "- Investigate account 8000EBD30 and explain suspicious activity.\n"
        "- Review recent transactions for account 8000EBD30.\n"
        "- Analyze account 8000EBD30 and explain which AML policy applies."
    )

    user_request = st.text_area(
        "Investigation Request",
        height=100,
        placeholder="Investigate account <account_number> for suspicious activity.",
    )

    if st.button("Investigate", type="primary"):
        if not user_request.strip():
            st.warning("Please enter an investigation request.")
        else:
            with st.spinner("Running investigation..."):
                try:
                    result = api_client.create_investigation(
                        token, user_request.strip()
                    )
                except APIError as exc:
                    handle_api_error(exc)
                    return
            st.session_state["last_investigation"] = result
            st.success("Investigation completed.")

    if st.session_state.get("last_investigation"):
        st.divider()
        ui.render_investigation_result(st.session_state["last_investigation"])


def _submit_decision(token: str, case_id: int, decision: str) -> None:
    with st.spinner(f"Submitting {decision}..."):
        try:
            outcome = api_client.submit_approval(token, case_id, decision)
        except APIError as exc:
            handle_api_error(exc)
            return

    st.success(f"Case {outcome['case_id']} {outcome['status']}.")

    try:
        st.session_state["last_case_lookup"] = api_client.get_case(token, case_id)
    except APIError:
        # Refresh is best-effort; the decision itself already succeeded.
        pass

    st.rerun()


def render_supervisor_approval_section(token: str) -> None:
    st.header("Case Review & Approval")

    case_id_input = int(st.number_input("Case ID", min_value=1, step=1, value=1))

    if st.button("Load Case"):
        try:
            st.session_state["last_case_lookup"] = api_client.get_case(
                token, case_id_input
            )
        except APIError as exc:
            handle_api_error(exc)
            return

    case = st.session_state.get("last_case_lookup")

    if not case or case.get("case_id") != case_id_input:
        st.caption("Enter a case ID and click 'Load Case' to review it.")
        return

    cols = st.columns(4)
    cols[0].metric("Case ID", case.get("case_id"))
    cols[1].metric("Account", case.get("account_number"))
    cols[2].metric("Risk Level", ui.risk_badge(case.get("risk_level")))
    cols[3].metric("Status", ui.status_badge(case.get("status")))
    st.caption(f"Created at: {case.get('created_at')}")

    last_investigation = st.session_state.get("last_investigation")
    if last_investigation and last_investigation.get("case_id") == case.get("case_id"):
        with st.expander(
            "Full investigation report / policy evidence (from this session)"
        ):
            ui.render_investigation_result(last_investigation)
    else:
        st.caption(
            "The full investigation report and policy evidence are only "
            "available at the time an investigation is run (they are "
            "not persisted for later retrieval by case ID)."
        )

    if case.get("risk_level") != "HIGH":
        st.info("Only HIGH-risk cases require supervisor approval/rejection.")
        return

    if case.get("status") != "OPEN":
        st.info(
            f"This case is not currently pending approval "
            f"(current status: {case.get('status')})."
        )
        return

    st.markdown("#### Decision")
    col_approve, col_reject = st.columns(2)

    if col_approve.button("✅ Approve", type="primary", use_container_width=True):
        _submit_decision(token, case_id_input, "approve")

    if col_reject.button("❌ Reject", use_container_width=True):
        _submit_decision(token, case_id_input, "reject")


def render_account_action_section(token: str) -> None:
    st.header("Controlled Account Status Update")
    st.caption(
        "The backend independently validates role, the case/account "
        "relationship, allowed state transitions, and (for freezing) "
        "that the referenced case is HIGH-risk and already approved. "
        "This form only submits the request - it does not decide "
        "whether the change is allowed."
    )

    with st.form("account_status_form"):
        account_number = st.text_input("Account Number")
        new_status = st.selectbox(
            "New Status", ["ACTIVE", "REVIEW", "FROZEN", "CLOSED"]
        )
        case_id = st.number_input("Related Case ID", min_value=1, step=1, value=1)
        submitted = st.form_submit_button("Submit Status Change", type="primary")

    if not submitted:
        return

    if not account_number.strip():
        st.warning("Please enter an account number.")
        return

    with st.spinner("Submitting account status change..."):
        try:
            outcome = api_client.update_account_status(
                token, account_number.strip(), new_status, int(case_id)
            )
        except APIError as exc:
            handle_api_error(exc)
            return

    st.success(
        f"Account {outcome['account_number']} status changed from "
        f"{outcome['previous_status']} to {outcome['new_status']} "
        f"(case {outcome['case_id']}, by {outcome['actor_username']})."
    )


def main() -> None:
    init_session_state()

    if not st.session_state.get("token"):
        render_login()
        return

    user = st.session_state["user"]
    ui.render_sidebar(user, api_client.API_BASE_URL, do_logout)

    st.title("🏦 Banking Transaction Investigation Agent")

    tab_labels = ["Investigator Dashboard"]
    if ui.can_supervise(user.get("role")):
        tab_labels += ["Supervisor: Approvals", "Supervisor: Account Actions"]

    tabs = st.tabs(tab_labels)

    with tabs[0]:
        render_investigator_dashboard(st.session_state["token"])

    if ui.can_supervise(user.get("role")):
        with tabs[1]:
            render_supervisor_approval_section(st.session_state["token"])
        with tabs[2]:
            render_account_action_section(st.session_state["token"])


if __name__ == "__main__":
    main()
