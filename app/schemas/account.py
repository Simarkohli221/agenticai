from typing import Literal

from pydantic import BaseModel

AccountStatus = Literal["ACTIVE", "REVIEW", "FROZEN", "CLOSED"]


class AccountStatusUpdateRequest(BaseModel):
    new_status: AccountStatus
    case_id: int


class AccountStatusUpdateResponse(BaseModel):
    account_number: str
    previous_status: str
    new_status: str
    case_id: int
    actor_username: str
    actor_role: str
