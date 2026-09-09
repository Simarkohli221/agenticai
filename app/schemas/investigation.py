from typing import Literal

from pydantic import BaseModel


class InvestigationRequest(BaseModel):
    user_request: str


class InvestigationResponse(BaseModel):
    case_id: int | None = None
    account_number: str | None = None
    risk_level: str | None = None
    risk_score: int | None = None
    approval_required: bool = False
    approval_status: str | None = None
    investigation_report: dict | None = None
    message: str | None = None
    # Already computed by the graph for this same request (customer
    # lookup, transaction retrieval) - surfaced here so a UI client
    # can render them without a second round trip or any new backend
    # computation. Not persisted; not returned by any other endpoint.
    customer: dict | None = None
    transactions: list[dict] | None = None


class CaseResponse(BaseModel):
    case_id: int
    account_number: str
    risk_level: str
    risk_score: int
    status: str
    created_at: str


class ApprovalRequest(BaseModel):
    decision: Literal["approve", "reject"]


class ApprovalResponse(BaseModel):
    case_id: int
    decision: str
    status: str | None = None
    risk_level: str | None = None
    actor_username: str | None = None
    actor_role: str | None = None
