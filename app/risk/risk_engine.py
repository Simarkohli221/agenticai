from decimal import Decimal


LARGE_TRANSACTION_THRESHOLD = Decimal("10000")


def analyze_risk(transactions: list[dict]) -> dict:
    indicators = []
    risk_score = 0

    if not transactions:
        return {
            "risk_level": "LOW",
            "risk_score": 0,
            "indicators": [],
            "transaction_count": 0
        }

    # Rule 1: Large transaction
    large_transactions = [
        tx for tx in transactions
        if Decimal(str(tx["amount_received"])) >= LARGE_TRANSACTION_THRESHOLD
    ]

    if large_transactions:
        risk_score += 30

        indicators.append({
            "type": "LARGE_TRANSACTION",
            "description": (
                f"{len(large_transactions)} transaction(s) "
                f"exceeded the large transaction threshold."
            )
        })

    # Rule 2: Multiple counterparties
    counterparties = set()

    for tx in transactions:
        if tx["from_account"]:
            counterparties.add(tx["from_account"])

        if tx["to_account"]:
            counterparties.add(tx["to_account"])

    if len(counterparties) >= 5:
        risk_score += 20

        indicators.append({
            "type": "MULTIPLE_COUNTERPARTIES",
            "description": (
                f"Activity involved {len(counterparties)} "
                f"distinct accounts."
            )
        })

    # Rule 3: Dataset laundering indicator
    laundering_transactions = [
        tx for tx in transactions
        if tx["is_laundering"]
    ]

    if laundering_transactions:
        risk_score += 50

        indicators.append({
            "type": "LAUNDERING_INDICATOR",
            "description": (
                f"{len(laundering_transactions)} transaction(s) "
                f"are labelled as laundering in the synthetic dataset."
            )
        })

    # Final risk classification
    if risk_score >= 50:
        risk_level = "HIGH"
    elif risk_score >= 30:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "risk_level": risk_level,
        "risk_score": min(risk_score, 100),
        "indicators": indicators,
        "transaction_count": len(transactions)
    }