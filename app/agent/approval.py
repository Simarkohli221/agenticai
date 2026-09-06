from langgraph.types import interrupt


def human_approval_node(state: dict) -> dict:
    risk_analysis = state.get("risk_analysis", {})
    customer = state.get("customer", {})

    approval_request = {
        "message": "High-risk investigation requires human approval.",
        "account_number": customer.get("account_number"),
        "entity_name": customer.get("entity_name"),
        "risk_level": risk_analysis.get("risk_level"),
        "risk_score": risk_analysis.get("risk_score"),
        "risk_indicators": risk_analysis.get("indicators", []),
    }

    decision = interrupt(approval_request)

    return {
        "approval_status": decision
    }