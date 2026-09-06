from app.db.database import SessionLocal
from app.tools.customer_tool import get_customer_account
from app.tools.transaction_tool import get_transactions
from app.tools.policy_tool import search_policy
from app.risk.risk_engine import analyze_risk


def get_customer_node(state: dict) -> dict:
    account_number = state["account_number"]

    db = SessionLocal()

    try:
        customer = get_customer_account(db, account_number)

        if customer is None:
            return {
                "error": f"Account {account_number} not found."
            }

        return {
            "customer": customer
        }

    finally:
        db.close()


def get_transactions_node(state: dict) -> dict:
    account_number = state["account_number"]

    db = SessionLocal()

    try:
        transactions = get_transactions(
            db,
            account_number,
            limit=20
        )

        return {
            "transactions": transactions
        }

    finally:
        db.close()


def search_policy_node(state: dict) -> dict:
    query = (
        "suspicious transaction "
        "high risk "
        "human review "
        "multiple accounts"
    )

    policy_results = search_policy(query)

    return {
        "policy_results": policy_results
    }
def analyze_risk_node(state: dict) -> dict:
    transactions = state.get("transactions", [])

    risk_analysis = analyze_risk(transactions)

    return {
        "risk_analysis": risk_analysis,
        "risk_level": risk_analysis["risk_level"],
        "approval_required": risk_analysis["risk_level"] == "HIGH"
    }
def generate_report_node(state: dict) -> dict:
    customer = state.get("customer", {})
    transactions = state.get("transactions", [])
    policy_results = state.get("policy_results", [])
    risk_analysis = state.get("risk_analysis", {})

    report = {
        "account": customer.get("account_number"),
        "entity": customer.get("entity_name"),
        "bank": customer.get("bank_name"),
        "transaction_count": len(transactions),
        "risk_level": risk_analysis.get("risk_level"),
        "risk_score": risk_analysis.get("risk_score"),
        "risk_indicators": risk_analysis.get("indicators", []),
        "policies": [
            policy["policy"]
            for policy in policy_results
        ],
        "recommendation": (
            "No immediate escalation required."
            if risk_analysis.get("risk_level") == "LOW"
            else "Further review required."
        )
    }

    return {
        "investigation_report": report
    }