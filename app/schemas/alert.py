from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int | None
    employee_code: str | None = None  # employee_code for frontend lookup
    employee_name: str | None = None  # employee name for display
    platform_id: int | None
    alert_type: str
    priority: str
    source_system: str
    reason: str
    detail: str | None
    status: str
    created_at: datetime
    resolved_at: datetime | None
