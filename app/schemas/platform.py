from datetime import date

from pydantic import BaseModel, ConfigDict


class PlatformCreate(BaseModel):
    name: str
    vendor: str
    category: str
    agreement_type: str
    license_type: str
    billing_period: str
    currency: str = "USD"
    inactivity_days: int = 30
    contractor_allowed: bool = True
    shared_allowed: bool = False
    api_available: bool = False
    notes: str | None = None
    effective_date: date | None = None
    renewal_date: date | None = None
    seat_cost: float | None = None
    enterprise_cost: float | None = None
    contracted_seats: int | None = None
    allocation_method: str | None = None


class PlatformRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    vendor: str
    category: str
    agreement_type: str
    license_type: str
    billing_period: str
    currency: str
    inactivity_days: int
    contractor_allowed: bool
    shared_allowed: bool
    api_available: bool
    notes: str | None
    effective_date: date | None
    renewal_date: date | None
    is_active: bool
