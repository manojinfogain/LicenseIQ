from pydantic import BaseModel, ConfigDict


class EmployeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_code: str
    full_name: str
    unit: str
    employment_status: str
    account_id: int
    project_id: int
    gdl_id: int | None
