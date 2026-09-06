def force_high_risk_node(state: dict) -> dict:
    return {
        "risk_analysis": {
            "risk_level": "HIGH",
            "risk_score": 80,
            "indicators": [
                {
                    "type": "TEST_HIGH_RISK",
                    "description": "Controlled HIGH-risk case for HITL testing."
                }
            ],
            "transaction_count": len(
                state.get("transactions", [])
            )
        },
        "risk_level": "HIGH",
        "approval_required": True
    }