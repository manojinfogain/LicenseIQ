from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    employee_count: int
    total_licenses: int
    active_licenses: int
    flagged_licenses: int
    monthly_spend: float
    open_alerts: int


class PlatformSeatSnapshotPoint(BaseModel):
    date: str
    seats: int


class PlatformUiRecord(BaseModel):
    id: int
    name: str
    vendor: str
    cat: str
    agr: str
    type: str
    billing: str
    currency: str
    seatCost: float
    entCost: float
    entSeats: int
    purchasedSeats: int
    alloc: str
    effectiveDate: str
    renewal: str
    activeSeats: int
    poolActiveSeats: int = 0
    inactiveDays: int
    contractor: str
    shared: str
    api: str
    notes: str


class LicenseUiRecord(BaseModel):
    plat: str
    cost: float
    type: str
    last: str
    st: str
    isCurrent: bool


class EmployeeUiRecord(BaseModel):
    id: str
    code: str = ""
    name: str
    unit: str
    proj: str
    proj_id: int | None = None
    acct: str
    acct_id: int | None = None
    acctOwner: str
    gdl: str
    status: str
    lics: list[LicenseUiRecord]
    assignments: list[dict] = []
    oracle_id: str = ""


class AlertUiRecord(BaseModel):
    empId: str
    empName: str | None = None
    type: str
    pri: str
    reason: str
    detail: str


class ManualAlertUiRecord(BaseModel):
    emp: str
    plat: str
    type: str
    proj: str
    by: str
    date: str
    cost: float
    pri: str


class QueueUiRecord(BaseModel):
    id: int
    source_id: int | None = None
    emp: str
    emp_id: int | None
    plat: str
    type: str
    proj: str
    by: str
    date: str
    cost: float
    status: str
    manual: bool
    approval_stage: str | None = None


class AllocationHistoryUiRecord(BaseModel):
    date: str
    action: str
    plat: str
    proj: str
    by: str


class ProjectMetaUiRecord(BaseModel):
    acct: str
    gdl: str


class DashboardBootstrapResponse(BaseModel):
    platforms: list[PlatformUiRecord]
    employees: list[EmployeeUiRecord]
    alerts: list[AlertUiRecord]
    manual_alerts: list[ManualAlertUiRecord]
    queue: list[QueueUiRecord]
    seat_snapshots: dict[str, list[PlatformSeatSnapshotPoint]]
    monthly_spend: dict[str, dict[str, list[float]]]
    monthly_project: dict[str, dict[str, list[float]]]
    alloc_hist: dict[str, list[AllocationHistoryUiRecord]]
    project_meta: dict[str, ProjectMetaUiRecord]
    units: list[str]
    accounts: list[str]
    projects: list[dict[str, int | str]]  # list of {id, name}
    gdls: list[str]
