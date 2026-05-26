"""
Aspire data service - Query Aspire database and return LicenseIQ-compatible data.
This bridges Aspire tables to the LicenseIQ dashboard without modifying any DB.

KEY FINDINGS from real Aspire data (verified):
  - EMP_ISACTIVE = '1' (active) or '0' (inactive) — NOT 'Y'/'N'
  - ACCOUNT_OWNER = EMP_STAFFID e.g. '107348' — NOT email
  - DeliveryHead  = EMP_STAFFID e.g. '108456' — NOT email
  - PROJECTMNGR_ID / OnsitePM / OffShorePM = EMP_STAFFID e.g. '107348' — NOT email
  - All char(20) fields have trailing spaces — use func.rtrim() for comparison
"""

from datetime import date, datetime, time

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.aspire_database import AspireSessionLocal
from app.models.aspire import (
    AspireAccount,
    AspireDeliveryUnit,
    AspireEmployee,
    AspireProject,
    AspireProjectAssignment,
)


def get_aspire_session() -> Session:
    """Open and return an Aspire database session (caller must close it)."""
    return AspireSessionLocal()


def _emp_with_relations():
    """Standard eager-load options for employees — avoids N+1 queries."""
    return [
        selectinload(AspireEmployee.project_assignments)
        .selectinload(AspireProjectAssignment.project)
        .selectinload(AspireProject.account),
        selectinload(AspireEmployee.project_assignments)
        .selectinload(AspireProjectAssignment.project)
        .selectinload(AspireProject.delivery_unit),
    ]


def _current_assignment_filters():
    """Return SQL filters for assignments that are current today on active/on-hold projects."""
    today_start = datetime.combine(date.today(), time.min)
    return (
        AspireProject.project_status.in_(["A", "O"]),
        or_(AspireProjectAssignment.project_startdate.is_(None), AspireProjectAssignment.project_startdate <= today_start),
        or_(AspireProjectAssignment.project_enddate.is_(None), AspireProjectAssignment.project_enddate >= today_start),
    )


def get_aspire_employees(db: Session, active_only: bool = True) -> list[AspireEmployee]:
    """Get all employees from Aspire. active_only filters by EMP_ISACTIVE='1'."""
    stmt = select(AspireEmployee).options(*_emp_with_relations())
    if active_only:
        stmt = stmt.where(func.rtrim(AspireEmployee.emp_isactive) == "1")
    return list(db.scalars(stmt).all())


def get_aspire_employees_by_account_owner(db: Session, owner_staffid: str) -> list[AspireEmployee]:
    """
    Get active employees in accounts owned by the given staff ID.
    Role: Account Owner — ACCOUNT_OWNER column stores EMP_STAFFID (e.g. '107348').
    """
    trimmed = owner_staffid.strip()
    return list(db.scalars(
        select(AspireEmployee)
        .join(AspireProjectAssignment, AspireEmployee.emp_staffid == AspireProjectAssignment.asg_emp_staffid)
        .join(AspireProject, AspireProjectAssignment.asg_project_id == AspireProject.project_id)
        .join(AspireAccount, AspireProject.account_id == AspireAccount.account_id)
        .where(
            func.rtrim(AspireEmployee.emp_isactive) == "1",
            func.rtrim(AspireAccount.account_owner) == trimmed,
            *_current_assignment_filters(),
        )
        .distinct()
        .options(*_emp_with_relations())
    ).all())


def get_aspire_employees_by_delivery_head(db: Session, head_staffid: str) -> list[AspireEmployee]:
    """
    Get active employees in delivery units headed by the given staff ID.
    Role: GDL Head — DeliveryHead column stores EMP_STAFFID (e.g. '108456').
    """
    trimmed = head_staffid.strip()
    return list(db.scalars(
        select(AspireEmployee)
        .join(AspireProjectAssignment, AspireEmployee.emp_staffid == AspireProjectAssignment.asg_emp_staffid)
        .join(AspireProject, AspireProjectAssignment.asg_project_id == AspireProject.project_id)
        .join(AspireDeliveryUnit, AspireProject.deliveryunit_id == AspireDeliveryUnit.deliveryunit_id)
        .where(
            func.rtrim(AspireEmployee.emp_isactive) == "1",
            func.rtrim(AspireDeliveryUnit.deliveryhead) == trimmed,
            *_current_assignment_filters(),
        )
        .distinct()
        .options(*_emp_with_relations())
    ).all())


def _pm_staffid_match_columns(trimmed: str):
    """Match legacy PM, onsite PM, or offshore PM on active projects."""
    return or_(
        func.rtrim(AspireProject.projectmngr_id) == trimmed,
        func.rtrim(AspireProject.onsite_pm) == trimmed,
        func.rtrim(AspireProject.offshore_pm) == trimmed,
    )


def is_aspire_delivery_head(db: Session, staffid: str) -> bool:
    trimmed = staffid.strip()
    found = db.scalar(
        select(AspireDeliveryUnit.deliveryunit_id)
        .where(
            func.rtrim(AspireDeliveryUnit.deliveryhead) == trimmed,
            func.rtrim(AspireDeliveryUnit.status) == "A",
        )
        .limit(1)
    )
    return found is not None


def is_aspire_account_owner(db: Session, staffid: str) -> bool:
    trimmed = staffid.strip()
    found = db.scalar(
        select(AspireAccount.account_id)
        .where(
            func.rtrim(AspireAccount.account_owner) == trimmed,
            func.rtrim(AspireAccount.account_status) == "A",
        )
        .limit(1)
    )
    return found is not None


def is_aspire_project_manager(db: Session, staffid: str) -> bool:
    trimmed = staffid.strip()
    found = db.scalar(
        select(AspireProject.project_id)
        .where(
            AspireProject.project_status.in_(["A", "O"]),
            _pm_staffid_match_columns(trimmed),
        )
        .limit(1)
    )
    return found is not None


def get_aspire_employees_by_project_manager(db: Session, pm_staffid: str) -> list[AspireEmployee]:
    """
    Get active employees on projects managed by the given staff ID.
    Role: Project Manager — PROJECTMNGR_ID, OnsitePM, or OffShorePM (staff ID).
    """
    trimmed = pm_staffid.strip()
    return list(db.scalars(
        select(AspireEmployee)
        .join(AspireProjectAssignment, AspireEmployee.emp_staffid == AspireProjectAssignment.asg_emp_staffid)
        .join(AspireProject, AspireProjectAssignment.asg_project_id == AspireProject.project_id)
        .where(
            func.rtrim(AspireEmployee.emp_isactive) == "1",
            _pm_staffid_match_columns(trimmed),
            *_current_assignment_filters(),
        )
        .distinct()
        .options(*_emp_with_relations())
    ).all())


def get_aspire_employees_by_account_id(db: Session, account_id: int) -> list[AspireEmployee]:
    """Get active employees assigned to ACTIVE projects in a specific Aspire account."""
    return list(db.scalars(
        select(AspireEmployee)
        .join(AspireProjectAssignment, AspireEmployee.emp_staffid == AspireProjectAssignment.asg_emp_staffid)
        .join(AspireProject, AspireProjectAssignment.asg_project_id == AspireProject.project_id)
        .where(
            func.rtrim(AspireEmployee.emp_isactive) == "1",
            AspireProject.account_id == account_id,
            *_current_assignment_filters(),
        )
        .distinct()
        .options(*_emp_with_relations())
    ).all())


def get_aspire_employees_by_project_id(db: Session, project_id: int) -> list[AspireEmployee]:
    """Get active employees assigned to a specific Aspire project."""
    return list(db.scalars(
        select(AspireEmployee)
        .join(AspireProjectAssignment, AspireEmployee.emp_staffid == AspireProjectAssignment.asg_emp_staffid)
        .join(AspireProject, AspireProjectAssignment.asg_project_id == AspireProject.project_id)
        .where(
            func.rtrim(AspireEmployee.emp_isactive) == "1",
            AspireProjectAssignment.asg_project_id == project_id,
            *_current_assignment_filters(),
        )
        .distinct()
        .options(*_emp_with_relations())
    ).all())


def get_aspire_employees_by_delivery_unit_id(db: Session, deliveryunit_id: int) -> list[AspireEmployee]:
    """Get active employees assigned to ACTIVE projects under a specific Aspire delivery unit."""
    return list(db.scalars(
        select(AspireEmployee)
        .join(AspireProjectAssignment, AspireEmployee.emp_staffid == AspireProjectAssignment.asg_emp_staffid)
        .join(AspireProject, AspireProjectAssignment.asg_project_id == AspireProject.project_id)
        .where(
            func.rtrim(AspireEmployee.emp_isactive) == "1",
            AspireProject.deliveryunit_id == deliveryunit_id,
            *_current_assignment_filters(),
        )
        .distinct()
        .options(*_emp_with_relations())
    ).all())


def get_aspire_employee_by_staffid(db: Session, staffid: str) -> AspireEmployee | None:
    """Get a single employee by staff ID."""
    return db.scalar(
        select(AspireEmployee)
        .where(func.rtrim(AspireEmployee.emp_staffid) == staffid.strip())
        .options(*_emp_with_relations())
    )


def get_emp_new_id_map(db: Session, staffids: list[str]) -> dict[str, str]:
    """Return {staff_id: emp_new_id} for the given staff IDs (active or inactive).
    Only includes entries where emp_new_id is non-empty."""
    if not staffids:
        return {}
    result: dict[str, str] = {}
    for i in range(0, len(staffids), 2000):
        chunk = staffids[i : i + 2000]
        rows = db.execute(
            select(AspireEmployee.emp_staffid, AspireEmployee.emp_new_id).where(
                AspireEmployee.emp_staffid.in_(chunk)
            )
        ).all()
        for staffid_val, new_id in rows:
            sid = (staffid_val or "").strip()
            nid = (new_id or "").strip()
            if sid and nid:
                result[sid] = nid
    return result


def get_aspire_accounts(db: Session) -> list[AspireAccount]:
    """Get all active accounts."""
    return list(db.scalars(
        select(AspireAccount)
        .where(func.rtrim(AspireAccount.account_status) == "A")
        .order_by(AspireAccount.account_name)
    ).all())


def get_aspire_delivery_units(db: Session) -> list[AspireDeliveryUnit]:
    """Get all active delivery units (GDLs)."""
    return list(db.scalars(
        select(AspireDeliveryUnit)
        .where(func.rtrim(AspireDeliveryUnit.status) == "A")
        .order_by(AspireDeliveryUnit.deliveryunit)
    ).all())


def get_aspire_projects(db: Session) -> list[AspireProject]:
    """Get all active/on-hold projects."""
    return list(db.scalars(
        select(AspireProject)
        .where(AspireProject.project_status.in_(["A", "O"]))
        .options(
            selectinload(AspireProject.account),
            selectinload(AspireProject.delivery_unit),
        )
        .order_by(AspireProject.project_name)
    ).all())

