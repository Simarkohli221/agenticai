"""
Reusable Streamlit rendering components for the investigation
dashboard. Purely presentational - no HTTP calls, no business logic,
no authorization decisions. Every value rendered here comes directly
from a backend API response; nothing is computed, guessed, or
invented in this file.

Role strings ("INVESTIGATOR", "SUPERVISOR", "ADMIN") are the same
plain-text values the backend's /auth/me endpoint returns. They are
used here ONLY to decide which UI sections to show - this is a
convenience, not a security boundary: every backend endpoint
independently re-checks the caller's role and resource permissions
regardless of what the frontend displays or hides.
"""

import streamlit as st
import pandas as pd

SUPERVISOR_ROLES = {"SUPERVISOR", "ADMIN"}

RISK_BADGE = {
    "HIGH": "🔴 HIGH",
    "MEDIUM": "🟠 MEDIUM",
    "LOW": "🟢 LOW",
}

STATUS_BADGE = {
    "OPEN": "🟡 OPEN",
    "UNDER_REVIEW": "🟠 UNDER_REVIEW",
    "APPROVED": "🟢 APPROVED",
    "REJECTED": "🔴 REJECTED",
    "CLOSED": "⚪ CLOSED",
}


def can_supervise(role: str | None) -> bool:
    return role in SUPERVISOR_ROLES


def risk_badge(risk_level: str | None) -> str:
    if not risk_level:
        return "Not available"
    return RISK_BADGE.get(risk_level, risk_level)


def status_badge(status_value: str | None) -> str:
    if not status_value:
        return "Not available"
    return STATUS_BADGE.get(status_value, status_value)


def render_sidebar(user: dict, api_base_url: str, on_logout) -> None:
    with st.sidebar:
        st.markdown("## 🏦 Banking Investigation Agent")
        st.divider()
        st.markdown(f"**User:** {user.get('username', '-')}")
        st.markdown(f"**Role:** {user.get('role', '-')}")
        st.caption(f"Backend: {api_base_url}")
        st.divider()
        if st.button("Log out", use_container_width=True):
            on_logout()


def render_case_card(result: dict) -> None:
    st.subheader("Case Information")

    case_id = result.get("case_id")
    account_number = result.get("account_number")
    risk_level = result.get("risk_level")
    approval_status = result.get("approval_status")

    cols = st.columns(4)
    cols[0].metric("Case ID", case_id if case_id is not None else "—")
    cols[1].metric("Account", account_number or "—")
    cols[2].metric("Risk Level", risk_badge(risk_level))
    cols[3].metric("Approval Status", approval_status or "N/A")

    if result.get("approval_required") and not approval_status:
        st.warning(
            result.get("message")
            or "This is a HIGH-risk investigation. Human approval is "
            "required before a full report can be generated."
        )


def render_customer_section(customer: dict | None) -> None:
    st.subheader("Customer Information")

    if not customer:
        st.info("No customer information was returned for this request.")
        return

    cols = st.columns(3)
    cols[0].markdown(f"**Account Number**\n\n{customer.get('account_number', '—')}")
    cols[1].markdown(f"**Bank**\n\n{customer.get('bank_name', '—')}")
    cols[2].markdown(f"**Bank ID**\n\n{customer.get('bank_id', '—')}")

    cols2 = st.columns(3)
    cols2[0].markdown(f"**Entity Name**\n\n{customer.get('entity_name', '—')}")
    cols2[1].markdown(f"**Entity ID**\n\n{customer.get('entity_id', '—')}")
    cols2[2].markdown(
        "**Account Status**\n\n"
        "Not available from this endpoint"
    )


def render_risk_section(report: dict) -> None:
    st.subheader("Risk Analysis")

    risk_level = report.get("risk_level")
    risk_score = report.get("risk_score")
    transaction_count = report.get("transaction_count")
    indicators = report.get("risk_indicators") or []

    cols = st.columns(3)
    cols[0].metric("Risk Level", risk_badge(risk_level))
    cols[1].metric("Risk Score", risk_score if risk_score is not None else "—")
    cols[2].metric(
        "Transactions Analyzed",
        transaction_count if transaction_count is not None else "—",
    )

    st.markdown("**Risk Indicators (deterministic risk engine)**")
    if indicators:
        for indicator in indicators:
            st.markdown(
                f"- `{indicator.get('type', 'UNKNOWN')}` — "
                f"{indicator.get('description', '')}"
            )
    else:
        st.caption("No risk indicators were raised for this account.")

    st.caption(
        "Risk level and score are computed entirely by the backend's "
        "deterministic risk engine. The frontend never calculates or "
        "modifies these values."
    )


def render_transactions_table(transactions: list[dict] | None) -> None:
    st.subheader("Transactions")

    if not transactions:
        st.info("No transaction data was returned for this request.")
        return

    rows = []
    for tx in transactions:
        rows.append({
            "Transaction ID": tx.get("transaction_id"),
            "Timestamp": tx.get("timestamp"),
            "From Account": tx.get("from_account"),
            "To Account": tx.get("to_account"),
            "Amount Received": tx.get("amount_received"),
            "Receiving Currency": tx.get("receiving_currency"),
            "Amount Paid": tx.get("amount_paid"),
            "Payment Currency": tx.get("payment_currency"),
            "Payment Format": tx.get("payment_format"),
            "Synthetic Dataset Flag": (
                "⚠️ flagged in training dataset" if tx.get("is_laundering") else ""
            ),
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if any(tx.get("is_laundering") for tx in transactions):
        st.warning(
            "One or more transactions carry a synthetic 'is_laundering' "
            "training-data label. This is a label from the synthetic "
            "dataset used to build this demo, NOT a real-world "
            "confirmed finding of criminal activity. Backend risk "
            "indicators (above) are the deterministic evidence to act on."
        )


def render_policy_evidence_section(report: dict) -> None:
    st.subheader("Policy Evidence")

    if report.get("policy_retrieval_unavailable"):
        st.error(
            "Policy evidence could not be retrieved due to a backend "
            "system error. No policy content is shown because none "
            "could be reliably retrieved."
        )
        return

    policy_evidence = report.get("policy_evidence") or []

    if not report.get("policy_evidence_found") or not policy_evidence:
        st.info("No relevant policy evidence was found for this request.")
        return

    st.caption("Retrieved policy evidence (semantic search over local AML policy documents):")

    for item in policy_evidence:
        with st.expander(f"{item.get('policy')} (chunk {item.get('chunk_id')})"):
            st.write(item.get("excerpt", ""))

    citations = report.get("policy_citations") or []
    if citations:
        st.markdown("**Citations:**")
        for citation in citations:
            st.markdown(f"- {citation}")


def render_ai_summary_section(report: dict) -> None:
    st.subheader("Investigation Report")
    st.caption(
        "🤖 AI-generated investigation summary — synthesized from the "
        "deterministic evidence above. This text does not itself "
        "determine risk, approval, or account actions."
    )

    summary = report.get("llm_summary")
    if summary:
        st.markdown(summary)
    else:
        st.info("No narrative summary is available for this request.")

    if report.get("status") == "ERROR":
        st.error(report.get("message", "The investigation could not be completed."))


def render_investigation_result(result: dict) -> None:
    report = result.get("investigation_report") or {}

    if report.get("status") == "ERROR":
        st.error(report.get("message", "The investigation could not be completed."))
        return

    is_policy_answer = report.get("status") == "POLICY_ANSWER"

    if not is_policy_answer:
        render_case_card(result)
        st.divider()

    render_customer_section(result.get("customer"))
    st.divider()

    if not is_policy_answer:
        render_risk_section(report)
        st.divider()
        render_transactions_table(result.get("transactions"))
        st.divider()

    render_policy_evidence_section(report)
    st.divider()
    render_ai_summary_section(report)
