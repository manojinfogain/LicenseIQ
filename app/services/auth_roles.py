"""
Resolve LicenseIQ application roles from LicenseIQ mappings and Aspire org data.

Priority:
  1. Active row in employee_wise_role_mappings (manual / admin-assigned)
  2. Aspire org position (GDL head, account owner, project manager) when enabled
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.aspire_database import AspireSessionLocal
from app.core.config import settings
from app.models.access import EmployeeWiseRoleMapping, Role
from app.services import aspire as aspire_svc
from app.services.phase1_integration import get_role_mapping_phase1

RoleSource = Literal["manual", "aspire_auto"]

# Display names for auto-detected roles (match seed_roles in seed_db.py)
_ASPIRE_AUTO_ROLE_NAMES: dict[str, str] = {
    "gdl": "GDL",
    "account": "Account Owner",
    "pm": "Project Manager",
}


@dataclass(frozen=True)
class ResolvedRole:
    code: str
    name: str
    scope_ref_id: int | None
    source: RoleSource


def _manual_mapping_from_db(db: Session, staffid: str) -> EmployeeWiseRoleMapping | None:
    return db.scalar(
        select(EmployeeWiseRoleMapping)
        .where(
            EmployeeWiseRoleMapping.emp_staffid == staffid.strip(),
            EmployeeWiseRoleMapping.is_active == True,  # noqa: E712
        )
        .options(selectinload(EmployeeWiseRoleMapping.role))
    )


def _manual_mapping_from_phase1(db: Session, staffid: str) -> ResolvedRole | None:
    """Use Phase 1 SP / ORM path; load full role name from DB when possible."""
    row = get_role_mapping_phase1(db, staffid)
    if not row or not row.get("role_code"):
        return None

    role_code = row["role_code"]
    scope_ref_id = row.get("scope_ref_id")
    role = db.scalar(select(Role).where(Role.code == role_code))
    role_name = role.name if role else role_code
    return ResolvedRole(
        code=role_code,
        name=role_name,
        scope_ref_id=scope_ref_id,
        source="manual",
    )


def detect_aspire_org_role(aspire_db: Session, staffid: str) -> ResolvedRole | None:
    """
    Infer application role from Aspire org structure.
    Priority when multiple hats: gdl > account > pm.
    """
    sid = staffid.strip()
    if not sid:
        return None

    if aspire_svc.is_aspire_delivery_head(aspire_db, sid):
        return ResolvedRole(code="gdl", name=_ASPIRE_AUTO_ROLE_NAMES["gdl"], scope_ref_id=None, source="aspire_auto")

    if aspire_svc.is_aspire_account_owner(aspire_db, sid):
        return ResolvedRole(
            code="account",
            name=_ASPIRE_AUTO_ROLE_NAMES["account"],
            scope_ref_id=None,
            source="aspire_auto",
        )

    if aspire_svc.is_aspire_project_manager(aspire_db, sid):
        return ResolvedRole(code="pm", name=_ASPIRE_AUTO_ROLE_NAMES["pm"], scope_ref_id=None, source="aspire_auto")

    return None


def resolve_user_role(
    db: Session,
    staffid: str,
    *,
    aspire_db: Session | None = None,
    allow_aspire_auto: bool | None = None,
) -> ResolvedRole | None:
    """
    Resolve effective role for a staff ID.

    Manual LicenseIQ mappings always win. Aspire auto-detection is optional
    (controlled by AUTH_ASPIRE_AUTO_ROLE / settings.auth_aspire_auto_role).
    """
    sid = (staffid or "").strip()
    if not sid:
        return None

    use_aspire_auto = (
        settings.auth_aspire_auto_role if allow_aspire_auto is None else allow_aspire_auto
    )

    # Phase 1 / ORM manual mapping
    phase1 = _manual_mapping_from_phase1(db, sid)
    if phase1:
        return phase1

    mapping = _manual_mapping_from_db(db, sid)
    if mapping and mapping.role:
        return ResolvedRole(
            code=mapping.role.code,
            name=mapping.role.name,
            scope_ref_id=mapping.scope_ref_id,
            source="manual",
        )

    if not use_aspire_auto:
        return None

    owns_aspire = aspire_db is not None
    adb = aspire_db if owns_aspire else AspireSessionLocal()
    try:
        return detect_aspire_org_role(adb, sid)
    finally:
        if not owns_aspire:
            adb.close()


def resolve_user_role_code(db: Session, staffid: str) -> str | None:
    """Convenience wrapper returning only role code."""
    resolved = resolve_user_role(db, staffid)
    return resolved.code if resolved else None
