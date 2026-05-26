from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.query_helpers import resolve_open_alerts_if_no_active_allocations
from app.models.license import AllocationAudit, LicenseAllocation
from app.models.organization import Employee


def resolve_assignment_scope(
    db: Session,
    *,
    employee_id: int,
    source_project_id: int | None,
    source_account_id: int | None,
    fallback_project_id: int | None,
) -> tuple[int | None, int | None]:
    employee = db.get(Employee, employee_id)
    resolved_project_id = source_project_id or fallback_project_id or (employee.project_id if employee else None)
    resolved_account_id = source_account_id or (employee.account_id if employee else None)
    return resolved_project_id, resolved_account_id


def create_assignment_allocation(
    db: Session,
    *,
    employee_id: int,
    platform_id: int,
    project_id: int | None,
    account_id: int | None,
    effective_date: date,
    monthly_cost: Decimal | float | None,
    changed_by_user_id: int | None,
    notes: str | None,
) -> LicenseAllocation:
    allocation = LicenseAllocation(
        employee_id=employee_id,
        platform_id=platform_id,
        project_id=project_id,
        account_id=account_id,
        status="active",
        effective_date=effective_date,
        monthly_cost=monthly_cost,
        source_type="queue",
    )
    db.add(allocation)
    db.flush()
    db.add(AllocationAudit(
        allocation_id=allocation.id,
        event_type="assigned",
        event_source="queue",
        old_status=None,
        new_status="active",
        changed_by_user_id=changed_by_user_id,
        notes=notes,
    ))
    return allocation


def revoke_active_allocation(
    db: Session,
    *,
    employee_lookup_ids: set[int],
    employee_id_for_alerts: int,
    platform_id: int,
    revoked_date: date,
    changed_by_user_id: int | None,
    notes: str | None,
) -> tuple[LicenseAllocation | None, int]:
    allocation = db.scalars(
        select(LicenseAllocation).where(
            LicenseAllocation.employee_id.in_(employee_lookup_ids),
            LicenseAllocation.platform_id == platform_id,
            LicenseAllocation.status == "active",
        )
    ).first()
    if allocation is None:
        return None, resolve_open_alerts_if_no_active_allocations(db, employee_id_for_alerts)

    old_status = allocation.status
    allocation.status = "inactive"
    allocation.revoked_date = revoked_date
    db.flush()
    db.add(AllocationAudit(
        allocation_id=allocation.id,
        event_type="revoked",
        event_source="queue",
        old_status=old_status,
        new_status="inactive",
        changed_by_user_id=changed_by_user_id,
        notes=notes,
    ))
    resolved_alerts = resolve_open_alerts_if_no_active_allocations(db, employee_id_for_alerts)
    return allocation, resolved_alerts
