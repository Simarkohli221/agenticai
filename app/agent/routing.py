def route_by_risk(state: dict) -> str:
    if state.get("risk_level") == "HIGH":
        return "high_risk"

    return "low_risk"