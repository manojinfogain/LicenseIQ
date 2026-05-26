from datetime import datetime

from pydantic import BaseModel, ConfigDict


class QueueItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_type: str
    source_id: int | None
    employee_id: int | None
    platform_id: int | None
    action_type: str
    project_id: int | None
    cost_snapshot_monthly: float | None
    requested_by_user_id: int | None
    assigned_to_user_id: int | None
    status: str
    executed_by_user_id: int | None
    executed_at: datetime | None
    execution_notes: str | None
    created_at: datetime


class QueueExecuteRequest(BaseModel):
    executed_by_user_id: int | None = None
    execution_notes: str | None = None
