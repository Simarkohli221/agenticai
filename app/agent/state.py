from typing import TypedDict


class InvestigationState(TypedDict, total=False):
    account_number: str
    user_request: str
    intent: str
    requested_information: list[str]
    customer: dict
    transactions: list[dict]
    policy_results: list[dict]
    policy_search_error: str | None
    risk_analysis: dict
    case_id: int
    investigation_report: dict

    risk_level: str
    approval_required: bool
    approval_status: str

    error: str