from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class LicenseRequestCreate(BaseModel):
    request_type: str
    employee_id: int
    platform_id: int
    project_id: int | None = None
    account_id: int | None = None
    requested_by_user_id: int | None = None
    requested_by_staffid: str | None = None
    justification: str | None = None
    effective_date: date | None = None


class LicenseRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_type: str
    employee_id: int
    platform_id: int
    project_id: int | None
    account_id: int | None
    requested_by_user_id: int | None
    requested_by_staffid: str | None = None
    justification: str | None
    effective_date: date | None
    approval_status: str
    approval_stage: str | None = None
    last_approver_user_id: int | None = None
    last_approval_time: datetime | None = None
    approval_notes: str | None = None
    created_at: datetime


class ApprovalHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    approval_stage: str
    approver_user_id: int | None
    approver_role: str
    action: str
    notes: str | None
    created_at: datetime
