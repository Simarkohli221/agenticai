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
