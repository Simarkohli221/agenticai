from app.db.database import SessionLocal
from app.tools.customer_tool import get_customer_account
from app.tools.transaction_tool import get_transactions
from app.tools.policy_tool import search_policy
from app.risk.risk_engine import analyze_risk
from app.agent.query_parser import parse_investigation_request
from app.agent.llm import generate_investigation_summary
from app.db.database import SessionLocal
from app.tools.case_tool import create_investigation_case
def parse_request_node(state: dict) -> dict:
    user_request = state["user_request"]

    parsed_request = parse_investigation_request(user_request)

    account_number = parsed_request.get("account_number")

    if not account_number:
        return {
            "error": "Could not identify an account number from the request."
        }

    return {
        "account_number": account_number
    }
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
def handle_error_node(state: dict) -> dict:
    return {
        "investigation_report": {
            "status": "ERROR",
            "message": state.get(
                "error",
                "Could not identify a valid account number."
            )
        }
    }
def generate_report_node(state: dict) -> dict:
    customer = state.get("customer", {})
    transactions = state.get("transactions", [])
    policy_results = state.get("policy_results", [])
    risk_analysis = state.get("risk_analysis", {})

    approval_status = state.get("approval_status")
    risk_level = risk_analysis.get("risk_level")

    if risk_level == "HIGH":
        if approval_status == "approve":
            recommendation = "Investigation approved for continued handling."
        elif approval_status == "reject":
            recommendation = (
                "Investigation rejected by human reviewer. "
                "No consequential action authorized."
            )
        else:
            recommendation = (
                "Human review required before consequential action."
            )

    elif risk_level == "LOW":
        recommendation = "No immediate escalation required."

    else:
        recommendation = "Further review required."

    evidence = {
        "account": customer.get("account_number"),
        "entity": customer.get("entity_name"),
        "bank": customer.get("bank_name"),
        "transaction_count": len(transactions),
        "risk_level": risk_level,
        "risk_score": risk_analysis.get("risk_score"),
        "risk_indicators": risk_analysis.get("indicators", []),
        "policies": [
            policy["policy"]
            for policy in policy_results
        ],
        "approval_status": approval_status,
        "recommendation": recommendation,
    }

    llm_summary = generate_investigation_summary(evidence)

    report = {
        **evidence,
        "llm_summary": llm_summary,
    }

    return {
        "investigation_report": report
    }
def create_case_node(state: dict) -> dict:
    account_number = state["account_number"]
    risk_analysis = state.get("risk_analysis", {})

    db = SessionLocal()

    try:
        case = create_investigation_case(
            db=db,
            account_number=account_number,
            risk_level=risk_analysis["risk_level"],
            risk_score=risk_analysis["risk_score"],
        )

        return {
            "case_id": case["case_id"]
        }

    finally:
        db.close()