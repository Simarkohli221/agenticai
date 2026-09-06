from typing import TypedDict


class InvestigationState(TypedDict, total=False):
    account_number: str

    customer: dict
    transactions: list[dict]
    policy_results: list[dict]
    risk_analysis: dict

    investigation_report: dict

    risk_level: str
    approval_required: bool
    approval_status: str

    error: str