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
    if state.get("error"):
        return "error"

    if not state.get("customer"):
        return "error"

    return "continue"