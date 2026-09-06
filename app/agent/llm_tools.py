from app.db.database import SessionLocal
from app.tools.customer_tool import get_customer_account
from app.db.database import SessionLocal
from app.tools.transaction_tool import get_transactions


def get_customer(account_number: str) -> dict:
    """
    Get customer and account information for a given account number.
    """

    db = SessionLocal()

    try:
        customer = get_customer_account(db, account_number)

        if customer is None:
            return {
                "error": f"Account {account_number} not found."
            }

        return customer

    finally:
        db.close()


def get_transactions_for_account(
    account_number: str,
    limit: int = 20
) -> list[dict]:
    """
    Get recent transactions for a given account number.
    """

    db = SessionLocal()

    try:
        return get_transactions(
            db,
            account_number,
            limit=limit
        )
    finally:
        db.close()
from app.tools.policy_tool import search_policy


def search_aml_policy(query: str) -> list[dict]:
    """
    Search AML policies relevant to a given investigation question.
    """
    return search_policy(query)
from app.risk.risk_engine import analyze_risk

def analyze_account_risk(account_number: str) -> dict:
    """
    Analyze recent transactions for an account
    using the deterministic risk engine.
    """

    transactions = get_transactions_for_account(
        account_number,
        limit=20
    )

    return analyze_risk(transactions)