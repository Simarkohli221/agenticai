from app.agent.llm_tools import (
    get_transactions_for_account,
    analyze_account_risk,
)


if __name__ == "__main__":
    account_number = "8000EBD30"

    transactions = get_transactions_for_account(account_number)

    risk = analyze_account_risk(transactions)

    print("=== Risk Analysis Tool Test ===")
    print(f"Account: {account_number}")
    print(f"Transactions analyzed: {len(transactions)}")
    print(f"Risk level: {risk['risk_level']}")
    print(f"Risk score: {risk['risk_score']}")

    print("\n=== Risk Indicators ===")

    for indicator in risk["indicators"]:
        print(f"- {indicator['type']}: {indicator['description']}")