from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.access import User
from app.models.license import Alert, LicenseAllocation, LicenseRequest, QueueItem
from app.models.organization import Employee


def validate_user_exists(db: Session, user_id: int | None, field_name: str) -> None:
    """Raise a 400 error when a provided user id does not exist."""
    if user_id is None:
        return
    if db.get(User, user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}: user id {user_id} does not exist",
        )


def resolve_employee_ids(db: Session, employee_id: int) -> set[int]:
    """Return candidate employee IDs for mixed PK/staff-ID storage."""
    from app.services.employee_resolution import resolve_canonical_employee_id

    ids: set[int] = {employee_id}
    try:
        ids.add(resolve_canonical_employee_id(db, employee_id))
    except HTTPException:
        pass
    real_employee = db.scalar(select(Employee).where(Employee.employee_code == str(employee_id)))
    if real_employee is not None:
        ids.add(real_employee.id)
    return ids


def find_active_allocation_id(
    db: Session,
    employee_ids: int | set[int],
    platform_id: int,
    *,
    status_value: str = "active",
) -> int | None:
    if isinstance(employee_ids, int):
        employee_filter = LicenseAllocation.employee_id == employee_ids
    else:
        employee_filter = LicenseAllocation.employee_id.in_(employee_ids)

    return db.scalar(
        select(LicenseAllocation.id).where(
            employee_filter,
            LicenseAllocation.platform_id == platform_id,
            LicenseAllocation.status == status_value,
        )
    )


def find_pending_request_id(
    db: Session,
    employee_ids: int | set[int],
    platform_id: int,
    request_type: str,
) -> int | None:
    if isinstance(employee_ids, int):
        employee_filter = LicenseRequest.employee_id == employee_ids
    else:
        employee_filter = LicenseRequest.employee_id.in_(employee_ids)

    return db.scalar(
        select(LicenseRequest.id).where(
            employee_filter,
            LicenseRequest.platform_id == platform_id,
            LicenseRequest.request_type == request_type,
            LicenseRequest.approval_status.in_(["submitted", "pending_approval", "pending_it_admin"]),
        )
    )


def find_pending_queue_item_id(
    db: Session,
    employee_ids: int | set[int],
    platform_id: int,
    action_type: str,
) -> int | None:
    if isinstance(employee_ids, int):
        employee_filter = QueueItem.employee_id == employee_ids
    else:
        employee_filter = QueueItem.employee_id.in_(employee_ids)

    return db.scalar(
        select(QueueItem.id).where(
            employee_filter,
            QueueItem.platform_id == platform_id,
            QueueItem.action_type == action_type,
            QueueItem.status == "pending",
        )
    )


def resolve_open_alerts_if_no_active_allocations(db: Session, employee_id: int) -> int:
    remaining_active = db.scalar(
        select(LicenseAllocation.id).where(
            LicenseAllocation.employee_id == employee_id,
            LicenseAllocation.status == "active",
        )
    )
    if remaining_active:
        return 0

    open_alerts = list(
        db.scalars(
            select(Alert).where(
                Alert.employee_id == employee_id,
                Alert.status == "open",
            )
        ).all()
    )
    if not open_alerts:
        return 0

    resolved_at = datetime.utcnow()
    for alert in open_alerts:
        alert.status = "resolved"
        alert.resolved_at = resolved_at
    return len(open_alerts)