from app.agent.planner import plan_tools, DEFAULT_INTENT


def route_by_risk(state: dict) -> str:
    if state.get("risk_level") == "HIGH":
        return "high_risk"

    return "low_risk"
def route_after_parsing(state: dict) -> str:
    if state.get("error"):
        return "error"

    if not state.get("account_number"):
        return "error"

    return "continue"
def route_after_customer_lookup(state: dict) -> str:
    """
    Gates on the customer lookup (unchanged behavior: "error" if it
    failed), then forks on the deterministic tool plan for the
    request's classified intent (see app/agent/planner.py). A
    POLICY_QUESTION intent's plan never includes "get_transactions",
    so it is routed to the lightweight policy-only path instead of
    the full transactions/risk/case/HITL investigation path.
    """
    if state.get("error"):
        return "error"

    if not state.get("customer"):
        return "error"

    intent = state.get("intent", DEFAULT_INTENT)
    plan = plan_tools(intent)

    if "get_transactions" in plan:
        return "full_investigation"

    return "policy_only"