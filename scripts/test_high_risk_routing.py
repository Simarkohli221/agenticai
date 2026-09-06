from app.agent.routing import route_by_risk


if __name__ == "__main__":

    low_state = {
        "risk_level": "LOW"
    }

    high_state = {
        "risk_level": "HIGH"
    }

    print("LOW:", route_by_risk(low_state))
    print("HIGH:", route_by_risk(high_state))