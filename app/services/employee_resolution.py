"""Resolve UI/Aspire employee references to local employees.id for allocations."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.aspire_database import AspireSessionLocal
from app.models.aspire import AspireEmployee
from app.models.organization import Employee
from app.services.bulk_import import _auto_create_local_employee, _resolve_aspire_employee_with_scope

logger = logging.getLogger(__name__)


def _lookup_aspire_staff_id(ref: str) -> str | None:
    """Map staff id or Emp_NewID to Aspire EMP_STAFFID."""
    normalized = (ref or "").strip()
    if not normalized:
        return None
    with AspireSessionLocal() as aspire_db:
        by_staff = aspire_db.scalar(
            select(AspireEmployee).where(func.rtrim(AspireEmployee.emp_staffid) == normalized)
        )
        if by_staff and by_staff.emp_staffid:
            return by_staff.emp_staffid.strip()
        by_new_id = aspire_db.scalar(
            select(AspireEmployee).where(func.rtrim(AspireEmployee.emp_new_id) == normalized)
        )
        if by_new_id and by_new_id.emp_staffid:
            return by_new_id.emp_staffid.strip()
    return None


def resolve_canonical_employee_id(db: Session, employee_ref: int | str) -> int:
    """
    Return local ``employees.id`` for license_allocations / license_requests.

    Accepts:
    - Local primary key
    - Aspire EMP_STAFFID (numeric string)
    - Emp_NewID (looked up in Aspire, then local row created if missing)
    """
    ref_str = str(employee_ref).strip()
    if not ref_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid employee reference.",
        )

    if ref_str.isdigit():
        by_pk = db.get(Employee, int(ref_str))
        if by_pk is not None:
            return by_pk.id

    by_code = db.scalar(select(Employee).where(Employee.employee_code == ref_str))
    if by_code is not None:
        return by_code.id

    staff_id = _lookup_aspire_staff_id(ref_str) or (ref_str if ref_str.isdigit() else None)
    if staff_id:
        existing = db.scalar(select(Employee).where(Employee.employee_code == staff_id))
        if existing is not None:
            return existing.id
        aspire_data = _resolve_aspire_employee_with_scope(staff_id)
        if aspire_data:
            created, err = _auto_create_local_employee(db, aspire_data)
            if created is not None:
                logger.info(
                    "Auto-created local employee id=%s for staff_id=%s (ref=%s)",
                    created.id,
                    staff_id,
                    ref_str,
                )
                return created.id
            if err:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=err,
                )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Employee not found for reference '{ref_str}'.",
    )
