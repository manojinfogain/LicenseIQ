from collections import defaultdict
from datetime import date, datetime, timedelta
from sqlalchemy import func, or_, select, text
import sqlalchemy as sa
from sqlalchemy.orm import Session, selectinload

from app.models.access import User, UserRoleAssignment, EmployeeWiseRoleMapping
from app.models.license import Alert, AllocationAudit, LicenseAllocation, LicenseRequest, QueueItem
from app.models.organization import Account, Employee, GDL, Project
from app.models.platform import Platform, PlatformSeatSnapshot
from app.schemas.dashboard import (
    AlertUiRecord,
    AllocationHistoryUiRecord,
    DashboardBootstrapResponse,
    DashboardSummaryResponse,
    EmployeeUiRecord,
    LicenseUiRecord,
    ManualAlertUiRecord,
    PlatformSeatSnapshotPoint,
    PlatformUiRecord,
    ProjectMetaUiRecord,
    QueueUiRecord,
)
from app.services.pricing import (
    calculate_platform_monthly_unit_cost_for_platform,
    money_float,
    resolve_allocation_monthly_cost,
)
from app.services import aspire as aspire_svc
from app.services.phase1_integration import get_role_mapping_phase1


MONTHS = list(range(1, 13))


def _fetch_dashboard_summary_metrics(db: Session, employee_ids: list[int]) -> tuple[int, int, int, float, int] | None:
    employee_ids_csv = ",".join(str(employee_id) for employee_id in employee_ids)
    try:
        row = db.execute(
            text("EXEC dbo.usp_GetDashboardSummaryMetrics @employee_ids=:employee_ids"),
            {"employee_ids": employee_ids_csv},
        ).mappings().one()
    except sa.exc.DBAPIError as exc:
        # Transitional fallback until the procedure is deployed in the app database.
        sa_exc = exc
        del sa_exc
        return None

    return (
        int(row["total_licenses"] or 0),
        int(row["active_licenses"] or 0),
        int(row["flagged_licenses"] or 0),
        float(row["monthly_spend"] or 0),
        int(row["open_alerts"] or 0),
    )


def _fmt_date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def _is_visible_alert(alert: Alert) -> bool:
    if alert.alert_type != "exit":
        return True
    reason = alert.reason or ""
    marker = "LWD "
    idx = reason.rfind(marker)
    if idx == -1:
        return True
    try:
        lwd = datetime.strptime(reason[idx + len(marker):idx + len(marker) + 10], "%d/%m/%Y").date()
    except ValueError:
        return True
    return lwd <= (datetime.utcnow().date() + timedelta(days=15))



def _fmt_short_date(value: date | None) -> str:
    if not value:
        return ""
    return value.strftime("%d/%m/%Y")



def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        return start, date(year, 12, 31)
    return start, date(year, month + 1, 1) - timedelta(days=1)



def _allocation_active_in_month(allocation: LicenseAllocation, year: int, month: int) -> bool:
    month_start, month_end = _month_bounds(year, month)
    effective_date = allocation.effective_date or month_start
    revoked_date = allocation.revoked_date
    if effective_date > month_end:
        return False
    if revoked_date and revoked_date < month_start:
        return False
    return True


def _allocation_is_current(allocation: LicenseAllocation) -> bool:
    return allocation.revoked_date is None


def _as_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _is_current_aspire_assignment(assignment, *, as_of: date | None = None) -> bool:
    if not assignment or not assignment.project:
        return False

    today = as_of or date.today()
    project_status = (assignment.project.project_status or "").strip()
    if project_status not in ("A", "O"):
        return False

    start_dt = _as_date(assignment.project_startdate)
    end_dt = _as_date(assignment.project_enddate)
    if start_dt and start_dt > today:
        return False
    if end_dt and end_dt <= today:
        return False
    return True


def _dashboard_years(allocations: list[LicenseAllocation]) -> list[int]:
    current_year = date.today().year
    if not allocations:
        return [current_year]

    start_year = min((allocation.effective_date or date.today()).year for allocation in allocations)
    end_year = max((allocation.revoked_date or date.today()).year for allocation in allocations)
    end_year = max(end_year, current_year)
    return list(range(start_year, end_year + 1))


def _get_role_by_staffid(db: Session, emp_staffid: str | None) -> tuple[str | None, int | None]:
    """Get role_code and scope_ref_id for an Aspire staff ID.

    Manual LicenseIQ mapping takes precedence; optional Aspire org auto-role
    when AUTH_ASPIRE_AUTO_ROLE is enabled (see auth_roles.resolve_user_role).
    """
    if not emp_staffid:
        return None, None

    from app.services.auth_roles import resolve_user_role

    resolved = resolve_user_role(db, emp_staffid)
    if not resolved:
        return None, None
    return resolved.code, resolved.scope_ref_id


def _get_user_scope(db: Session, user_id: int | None) -> tuple[User | None, str | None, int | None, str | None]:
    """Return (user, role_code, scope_ref_id, aspire_staff_id).
    DEPRECATED: Use _get_role_by_staffid() with staffid directly instead.
    Kept for backward compatibility with user_id-based lookups.
    """
    if not user_id:
        return None, None, None, None

    current_user = db.scalar(
        select(User)
        .where(User.id == user_id)
    )
    if not current_user:
        return None, None, None, None
    
    aspire_staff_id = getattr(current_user, "aspire_staff_id", None)
    if not aspire_staff_id:
        # Fallback to old UserRoleAssignment for users without aspire_staff_id
        user_with_roles = db.scalar(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.role_assignments).selectinload(UserRoleAssignment.role))
        )
        if user_with_roles and user_with_roles.role_assignments:
            assignment = user_with_roles.role_assignments[0]
            role_code = assignment.role.code if assignment.role else None
            return current_user, role_code, assignment.scope_ref_id, None
        return current_user, None, None, None
    
    # Use EmployeeWiseRoleMapping with the Aspire staff ID
    role_code, scope_ref_id = _get_role_by_staffid(db, aspire_staff_id)
    return current_user, role_code, scope_ref_id, aspire_staff_id


class _EmpProxy:
    """Lightweight proxy that mimics the Employee ORM object for dashboard rendering.
    Used when data comes from Aspire instead of the LicenseIQ employees table.
    """
    __slots__ = (
        "id", "employee_code", "full_name", "unit", "employment_status",
        "account_id", "project_id", "gdl_id", "account_owner_user_id",
        "_aspire_account_name", "_aspire_project_name", "_aspire_du_code",
        "_aspire_account_owner_staffid", "_aspire_account_owner_name",
        "_all_assignments", "_oracle_id",
    )

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _aspire_employees_to_licenseiq(
    aspire_emps: list,
    *,
    filter_account_id: int | None = None,
    filter_project_id: int | None = None,
    filter_gdl_id: int | None = None,
    filter_account_owner_staffid: str | None = None,
    filter_delivery_head_staffid: str | None = None,
) -> list:
    """
    Convert AspireEmployee objects to _EmpProxy objects that
    the dashboard templates can consume without touching the LicenseIQ tables.
    
    Optional filter parameters ensure that when scoped to a specific account/project/GDL,
    the proxy uses the employee's assignment from THAT scope, not their first active project.
    """
    def _best_assignment(assignments, predicate=None):
        filtered = [a for a in (assignments or []) if predicate(a)] if predicate else list(assignments or [])
        if not filtered:
            return None

        def _key(assignment):
            end_dt = assignment.project_enddate or datetime.max
            start_dt = assignment.project_startdate or datetime.min
            stamp_dt = getattr(assignment, "asg_timestamp", None) or datetime.min
            project_id = assignment.asg_project_id or 0
            return (end_dt, start_dt, stamp_dt, project_id)

        return max(filtered, key=_key)

    result = []
    for ae in aspire_emps:
        staff_id_str = (ae.emp_staffid or "").strip()
        try:
            synthetic_id = int(staff_id_str)
        except ValueError:
            synthetic_id = abs(hash(staff_id_str)) % (10 ** 9)

        # Pick the assignment matching the filter, or fall back to first active project
        _today = date.today()

        def _is_current(a):
            """Python-side date check matching _current_assignment_filters() SQL logic."""
            start_date = a.project_startdate.date() if getattr(a, "project_startdate", None) else None
            end_date = a.project_enddate.date() if getattr(a, "project_enddate", None) else None
            return (
                (start_date is None or start_date <= _today)
                and (end_date is None or end_date >= _today)
            )

        pa = None
        if filter_account_id:
            pa = _best_assignment(
                ae.project_assignments,
                lambda a: _is_current_aspire_assignment(a)
                and a.project.account_id == filter_account_id,
            )
        elif filter_account_owner_staffid:
            trimmed_owner_staffid = filter_account_owner_staffid.strip()
            pa = _best_assignment(
                ae.project_assignments,
                lambda a: _is_current_aspire_assignment(a)
                and a.project.account and (a.project.account.account_owner or "").strip() == trimmed_owner_staffid,
            )
        elif filter_project_id:
            pa = _best_assignment(
                ae.project_assignments,
                lambda a: _is_current_aspire_assignment(a)
                and a.project.project_id == filter_project_id,
            )
        elif filter_gdl_id:
            pa = _best_assignment(
                ae.project_assignments,
                lambda a: _is_current_aspire_assignment(a)
                and a.project.deliveryunit_id == filter_gdl_id,
            )
        elif filter_delivery_head_staffid:
            trimmed_delivery_head_staffid = filter_delivery_head_staffid.strip()
            pa = _best_assignment(
                ae.project_assignments,
                lambda a: _is_current_aspire_assignment(a)
                and a.project.delivery_unit
                and (a.project.delivery_unit.deliveryhead or "").strip() == trimmed_delivery_head_staffid,
            )

        # Fallback: current active project, then active project, then first assignment
        if not pa:
            pa = _best_assignment(
                ae.project_assignments,
                _is_current_aspire_assignment,
            ) or _best_assignment(
                ae.project_assignments,
                lambda a: a.project and (a.project.project_status or "").strip() in ("A", "O"),
            ) or _best_assignment(ae.project_assignments)
        
        proj = pa.project if pa else None
        acc = proj.account if proj else None
        du = proj.delivery_unit if proj else None

        owner_staffid = (acc.account_owner or "").strip() if acc else ""

        display_id = (ae.emp_new_id or "").strip() or staff_id_str
        result.append(_EmpProxy(
            id=synthetic_id,
            employee_code=display_id,
            full_name=ae.full_name or staff_id_str,
            unit=(du.deliveryunit or "").strip() if du else (acc.account_name or "").strip() if acc else "Unassigned",
            employment_status="active" if ae.is_active else "inactive",
            account_id=acc.account_id if acc else None,
            project_id=proj.project_id if proj else None,
            gdl_id=du.deliveryunit_id if du else None,
            account_owner_user_id=None,
            _aspire_account_owner_staffid=owner_staffid,
            _aspire_account_owner_name="",
            _aspire_account_name=acc.account_name if acc else "",
            _aspire_project_name=proj.project_name if proj else "",
            _aspire_du_code=du.deliveryunit if du else "",
            _oracle_id=(proj.oracle_project_id or "").strip() if proj else "",
            _all_assignments=[
                {
                    "acct": (a.project.account.account_name or "") if a.project and a.project.account else "",
                    "proj": (a.project.project_name or "") if a.project else "",
                    "proj_id": a.project.project_id if a.project else None,
                }
                for a in (ae.project_assignments or [])
                if _is_current_aspire_assignment(a)
                   and (a.project.project_name or "").strip()
            ],
        ))
    return result


def _get_primary_aspire_scope(aspire_employee) -> tuple[int | None, int | None, int | None]:
    """Return (account_id, project_id, deliveryunit_id) from the employee's primary active Aspire assignment."""
    if not aspire_employee:
        return None, None, None

    assignments = aspire_employee.project_assignments or []

    def _scope_key(assignment):
        end_dt = assignment.project_enddate or datetime.max
        start_dt = assignment.project_startdate or datetime.min
        stamp_dt = getattr(assignment, "asg_timestamp", None) or datetime.min
        project_id = assignment.asg_project_id or 0
        return (end_dt, start_dt, stamp_dt, project_id)

    current_active_assignments = [
        assignment
        for assignment in assignments
        if _is_current_aspire_assignment(assignment)
    ]
    active_assignments = [
        assignment
        for assignment in assignments
        if assignment.project and (assignment.project.project_status or "").strip() in ("A", "O")
    ]
    primary_assignment = (
        max(current_active_assignments, key=_scope_key)
        if current_active_assignments
        else (
            max(active_assignments, key=_scope_key)
            if active_assignments
            else (max(assignments, key=_scope_key) if assignments else None)
        )
    )
    project = primary_assignment.project if primary_assignment else None
    account = project.account if project else None
    delivery_unit = project.delivery_unit if project else None
    return (
        account.account_id if account else None,
        project.project_id if project else None,
        delivery_unit.deliveryunit_id if delivery_unit else None,
    )


def _scoped_employees(
    db: Session,
    user_id: int | None = None,
    staffid: str | None = None,
    *,
    org_level: bool = False,
    account_id: int | None = None,
    project_id: int | None = None,
    gdl_id: int | None = None,
    unit: str | None = None,
) -> list[Employee]:
    """Get employees scoped by user role.
    
    Supports two modes:
    1. staffid: Direct Aspire staff ID (recommended, uses EmployeeWiseRoleMapping)
    2. user_id: Legacy LicenseIQ user ID (uses User + aspire_staff_id link)
    """
    if org_level:
        adb = aspire_svc.get_aspire_session()
        try:
            aspire_emps = aspire_svc.get_aspire_employees(adb, active_only=True)
            proxies = _aspire_employees_to_licenseiq(aspire_emps)
            staff_id_strings = [str(p.id) for p in proxies]
            if staff_id_strings:
                local_id_map: dict[str, int] = {}
                for i in range(0, len(staff_id_strings), 2000):
                    chunk = staff_id_strings[i:i + 2000]
                    rows = db.execute(
                        select(Employee.employee_code, Employee.id).where(
                            Employee.employee_code.in_(chunk)
                        )
                    ).all()
                    local_id_map.update({row[0]: row[1] for row in rows})
                for proxy in proxies:
                    real_id = local_id_map.get(str(proxy.id))
                    if real_id is not None:
                        proxy.id = real_id

            # Supplement with all local employees with active allocations not in proxies
            resolved_real_ids = {p.id for p in proxies}
            all_allocated = db.scalars(
                select(Employee).join(
                    LicenseAllocation, LicenseAllocation.employee_id == Employee.id
                ).where(
                    LicenseAllocation.status == "active"
                ).distinct()
            ).all()
            supp_emps = [emp for emp in all_allocated if emp.id not in resolved_real_ids]
            supp_new_id_map = aspire_svc.get_emp_new_id_map(adb, [e.employee_code for e in supp_emps])
            for emp in supp_emps:
                proxies.append(_EmpProxy(
                    id=emp.id,
                    employee_code=supp_new_id_map.get(emp.employee_code) or emp.employee_code,
                    full_name=emp.full_name,
                    unit=emp.unit or "",
                    employment_status=emp.employment_status,
                    account_id=emp.account_id,
                    project_id=emp.project_id,
                    gdl_id=emp.gdl_id,
                    account_owner_user_id=emp.account_owner_user_id,
                    _aspire_account_name="",
                    _aspire_project_name="",
                    _aspire_du_code="",
                    _aspire_account_owner_staffid="",
                    _aspire_account_owner_name="",
                    _all_assignments=[],
                ))
        finally:
            adb.close()
        return proxies

    # Mode 1: Direct staffid lookup (PlanningMonitoring style)
    if staffid:
        user_role, user_scope_ref_id = _get_role_by_staffid(db, staffid)
        aspire_staff_id = staffid.strip()
        current_user = None
    # Mode 2: Legacy user_id lookup
    else:
        current_user, user_role, user_scope_ref_id, aspire_staff_id = _get_user_scope(db, user_id)

    # ── Aspire path: use real Aspire data when staffid or aspire_staff_id is available ─────
    if aspire_staff_id:
        adb = aspire_svc.get_aspire_session()
        try:
            sid = aspire_staff_id.strip()
            own_aspire_employee = None
            own_account_id = None
            own_project_id = None
            own_gdl_id = None

            if user_role == "pm" and not user_scope_ref_id:
                own_aspire_employee = aspire_svc.get_aspire_employee_by_staffid(adb, sid)
                own_account_id, own_project_id, own_gdl_id = _get_primary_aspire_scope(own_aspire_employee)

            # Determine which scope filters to use for assignment selection
            filter_account_id = None
            filter_project_id = None
            filter_gdl_id = None
            filter_account_owner_staffid = None
            filter_delivery_head_staffid = None

            if user_role in ("admin", "finance") or not user_role:
                aspire_emps = aspire_svc.get_aspire_employees(adb, active_only=True)
            elif user_role == "account":
                if user_scope_ref_id:
                    aspire_emps = aspire_svc.get_aspire_employees_by_account_id(adb, user_scope_ref_id)
                    filter_account_id = user_scope_ref_id
                else:
                    aspire_emps = aspire_svc.get_aspire_employees_by_account_owner(adb, sid)
                    filter_account_owner_staffid = sid
            elif user_role == "gdl":
                if user_scope_ref_id:
                    aspire_emps = aspire_svc.get_aspire_employees_by_delivery_unit_id(adb, user_scope_ref_id)
                    filter_gdl_id = user_scope_ref_id
                else:
                    aspire_emps = aspire_svc.get_aspire_employees_by_delivery_head(adb, sid)
                    filter_delivery_head_staffid = sid
            elif user_role == "pm":
                if user_scope_ref_id:
                    aspire_emps = aspire_svc.get_aspire_employees_by_project_id(adb, user_scope_ref_id)
                    filter_project_id = user_scope_ref_id
                elif own_project_id:
                    aspire_emps = aspire_svc.get_aspire_employees_by_project_id(adb, own_project_id)
                    filter_project_id = own_project_id
                else:
                    aspire_emps = aspire_svc.get_aspire_employees_by_project_manager(adb, sid)
            else:
                aspire_emps = aspire_svc.get_aspire_employees(adb, active_only=True)
            proxies = _aspire_employees_to_licenseiq(
                aspire_emps,
                filter_account_id=filter_account_id,
                filter_project_id=filter_project_id,
                filter_gdl_id=filter_gdl_id,
                filter_account_owner_staffid=filter_account_owner_staffid,
                filter_delivery_head_staffid=filter_delivery_head_staffid,
            )
            # ── Resolve proxy IDs to real employees.id from the local DB ──────────
            # _EmpProxy.id defaults to int(aspire_staff_id) which does NOT match
            # license_allocations.employee_id (a FK to employees.id auto-increment).
            # employees.employee_code stores the Aspire staff_id string, and proxy.id
            # stores int(aspire_staff_id), so look up by str(proxy.id).
            staff_id_strings = [str(p.id) for p in proxies]
            if staff_id_strings:
                local_id_map: dict[str, int] = {}
                for i in range(0, len(staff_id_strings), 2000):
                    chunk = staff_id_strings[i:i + 2000]
                    rows = db.execute(
                        select(Employee.employee_code, Employee.id).where(
                            Employee.employee_code.in_(chunk)
                        )
                    ).all()
                    local_id_map.update({row[0]: row[1] for row in rows})
                for proxy in proxies:
                    real_id = local_id_map.get(str(proxy.id))
                    if real_id is not None:
                        proxy.id = real_id

            # ── Admin/Finance: supplement with local employees that have allocations
            # but weren't returned by Aspire (inactive staff, contractors, etc.) ───
            if user_role in ("admin", "finance") or not user_role:
                resolved_real_ids = {p.id for p in proxies}
                # Find all local employees with active allocations, fetching in small
                # batches to avoid SQL Server parameter limits on NOT IN.
                all_allocated = db.scalars(
                    select(Employee).join(
                        LicenseAllocation, LicenseAllocation.employee_id == Employee.id
                    ).where(
                        LicenseAllocation.status == "active"
                    ).distinct()
                ).all()
                supp_emps = [emp for emp in all_allocated if emp.id not in resolved_real_ids]
                supp_new_id_map = aspire_svc.get_emp_new_id_map(adb, [e.employee_code for e in supp_emps])
                for emp in supp_emps:
                    proxies.append(_EmpProxy(
                        id=emp.id,
                        employee_code=supp_new_id_map.get(emp.employee_code) or emp.employee_code,
                        full_name=emp.full_name,
                        unit=emp.unit or "",
                        employment_status=emp.employment_status,
                        account_id=emp.account_id,
                        project_id=emp.project_id,
                        gdl_id=emp.gdl_id,
                        account_owner_user_id=emp.account_owner_user_id,
                        _aspire_account_name="",
                        _aspire_project_name="",
                        _aspire_du_code="",
                        _aspire_account_owner_staffid="",
                        _aspire_account_owner_name="",
                        _all_assignments=[],
                    ))
        finally:
            adb.close()
        return proxies

    # ── Fallback: LicenseIQ mock employee table ────────────────────────────────
    emp_stmt = select(Employee).order_by(Employee.full_name)

    if user_role == "account" and user_id:
        emp_stmt = emp_stmt.join(Account, Employee.account_id == Account.id).where(
            or_(Employee.account_owner_user_id == user_id, Account.owner_user_id == user_id)
        )
        if user_scope_ref_id:
            emp_stmt = emp_stmt.where(Employee.account_id == user_scope_ref_id)
    elif user_role == "pm" and user_id:
        scoped_project_ids = set(db.scalars(select(Project.id).where(Project.project_manager_user_id == user_id)).all())
        if not scoped_project_ids and current_user:
            scoped_project_ids.update(
                db.scalars(select(Employee.project_id).where(Employee.full_name == current_user.full_name)).all()
            )
        if user_scope_ref_id:
            scoped_project_ids.add(user_scope_ref_id)
        if scoped_project_ids:
            emp_stmt = emp_stmt.where(Employee.project_id.in_(sorted(scoped_project_ids)))
        else:
            emp_stmt = emp_stmt.where(Employee.id == -1)
    elif user_role == "gdl" and user_id:
        scoped_gdl_ids: set[int] = set()
        if user_scope_ref_id:
            scoped_gdl_ids.add(user_scope_ref_id)
        elif current_user:
            scoped_gdl_ids.update(
                gdl_id_value
                for gdl_id_value in db.scalars(
                    select(Employee.gdl_id).where(Employee.full_name == current_user.full_name)
                ).all()
                if gdl_id_value is not None
            )
        if scoped_gdl_ids:
            emp_stmt = emp_stmt.where(Employee.gdl_id.in_(sorted(scoped_gdl_ids)))

    if account_id:
        emp_stmt = emp_stmt.where(Employee.account_id == account_id)
    if project_id:
        emp_stmt = emp_stmt.where(Employee.project_id == project_id)
    if gdl_id:
        emp_stmt = emp_stmt.where(Employee.gdl_id == gdl_id)
    if unit:
        emp_stmt = emp_stmt.where(Employee.unit == unit)

    return list(db.scalars(emp_stmt).all())




def build_dashboard_summary(
    db: Session,
    user_id: int | None = None,
    staffid: str | None = None,
    account_id: int | None = None,
    project_id: int | None = None,
    gdl_id: int | None = None,
    unit: str | None = None,
    account_name: str | None = None,
    project_name: str | None = None,
    gdl_code: str | None = None,
) -> DashboardSummaryResponse:
    # Resolve name-based params to IDs when IDs are not provided
    if account_name and not account_id:
        acc = db.scalar(select(Account).where(Account.name == account_name))
        account_id = acc.id if acc else -1
    if project_name and not project_id:
        proj = db.scalar(select(Project).where(Project.name == project_name))
        project_id = proj.id if proj else -1
    if gdl_code and not gdl_id:
        gdl = db.scalar(select(GDL).where(GDL.code == gdl_code))
        gdl_id = gdl.id if gdl else -1

    employees = _scoped_employees(
        db,
        user_id,
        staffid=staffid,
        account_id=account_id,
        project_id=project_id,
        gdl_id=gdl_id,
        unit=unit,
    )
    # Deduplicate employee IDs to keep chunked summary counts stable and consistent.
    employee_ids = sorted({employee.id for employee in employees})
    if not employee_ids:
        return DashboardSummaryResponse(
            employee_count=0,
            total_licenses=0,
            active_licenses=0,
            flagged_licenses=0,
            monthly_spend=0,
            open_alerts=0,
        )

    # Employees assigned = distinct employees with at least one current allocation.
    employees_assigned = 0
    for i in range(0, len(employee_ids), 2000):
        chunk = employee_ids[i:i + 2000]
        employees_assigned += db.scalar(
            select(func.count(func.distinct(LicenseAllocation.employee_id))).where(
                LicenseAllocation.employee_id.in_(chunk),
                LicenseAllocation.revoked_date.is_(None),
            )
        ) or 0

    summary_metrics = _fetch_dashboard_summary_metrics(db, employee_ids)
    if summary_metrics is not None:
        total_licenses, active_licenses, flagged_licenses, monthly_spend, open_alerts = summary_metrics
        return DashboardSummaryResponse(
            employee_count=int(employees_assigned),
            total_licenses=total_licenses,
            active_licenses=active_licenses,
            flagged_licenses=flagged_licenses,
            monthly_spend=monthly_spend,
            open_alerts=open_alerts,
        )

    # SQL Server 2100-param limit: chunk large IN() lists
    def _count_alloc(extra_filters: list) -> int:
        total = 0
        for i in range(0, len(employee_ids), 2000):
            chunk = employee_ids[i:i + 2000]
            total += db.scalar(
                select(func.count(LicenseAllocation.id)).where(
                    LicenseAllocation.employee_id.in_(chunk),
                    LicenseAllocation.revoked_date.is_(None),
                    *extra_filters,
                )
            ) or 0
        return total

    def _sum_alloc() -> float:
        total = 0.0
        for i in range(0, len(employee_ids), 2000):
            chunk = employee_ids[i:i + 2000]
            total += float(db.scalar(
                select(func.coalesce(func.sum(LicenseAllocation.monthly_cost), 0)).where(
                    LicenseAllocation.employee_id.in_(chunk),
                    LicenseAllocation.revoked_date.is_(None),
                )
            ) or 0)
        return total

    def _count_alerts() -> int:
        total = 0
        for i in range(0, len(employee_ids), 2000):
            chunk = employee_ids[i:i + 2000]
            total += db.scalar(
                select(func.count(Alert.id)).where(
                    Alert.employee_id.in_(chunk), Alert.status == "open"
                )
            ) or 0
        return total

    total_licenses = _count_alloc([])
    active_licenses = _count_alloc([LicenseAllocation.status == "active"])
    flagged_licenses = _count_alloc([LicenseAllocation.status != "active"])
    monthly_spend = _sum_alloc()
    open_alerts = _count_alerts()

    return DashboardSummaryResponse(
        employee_count=int(employees_assigned),
        total_licenses=int(total_licenses),
        active_licenses=int(active_licenses),
        flagged_licenses=int(flagged_licenses),
        monthly_spend=float(monthly_spend),
        open_alerts=int(open_alerts),
    )



def build_dashboard_bootstrap(
    db: Session,
    user_id: int | None = None,
    staffid: str | None = None,
    org_level: bool = False,
) -> DashboardBootstrapResponse:
    """Build dashboard bootstrap data scoped to user role.
    
    Supports two modes:
    1. staffid: Direct Aspire staff ID (recommended, uses EmployeeWiseRoleMapping)
    2. user_id: Legacy LicenseIQ user ID (uses User + aspire_staff_id link)
    
    If both provided, staffid takes precedence.
    """
    platforms = list(
        db.scalars(
            select(Platform).options(selectinload(Platform.contracts)).order_by(Platform.name)
        ).all()
    )
    seat_snapshots = list(
        db.scalars(select(PlatformSeatSnapshot).order_by(PlatformSeatSnapshot.snapshot_date)).all()
    )

    employees = _scoped_employees(db, user_id=user_id, staffid=staffid, org_level=org_level)
    is_aspire = employees and not isinstance(employees[0], Employee)
    # Aspire synthetic IDs (int(staffid)) are stored directly in queue_items/requests/etc,
    # so we can always filter by employee_id — no empty-set special-case needed.
    employee_ids: set[int] = {emp.id for emp in employees}
    employee_codes_for_ids = list({
        (getattr(emp, "employee_code", None) or "").strip()
        for emp in employees
        if getattr(emp, "employee_code", None)
    } - {""})
    if employee_codes_for_ids:
        try:
            for i in range(0, len(employee_codes_for_ids), 1500):
                chunk = employee_codes_for_ids[i:i + 1500]
                employee_ids.update(
                    db.scalars(select(Employee.id).where(Employee.employee_code.in_(chunk))).all()
                )
        except Exception:
            pass

    # SQL Server has a 2100-parameter limit on IN(); chunk if needed.
    def _in_chunks(model_col, ids: set[int]):
        ids_list = list(ids)
        results = []
        for i in range(0, len(ids_list), 2000):
            chunk = ids_list[i:i + 2000]
            results.extend(db.scalars(select(model_col.class_).where(model_col.in_(chunk))).all())
        return results

    try:
        allocations = _in_chunks(LicenseAllocation.employee_id, employee_ids) if employee_ids else []
    except Exception:
        allocations = []
    allocation_ids = {allocation.id for allocation in allocations}

    scoped_alerts = _in_chunks(Alert.employee_id, employee_ids) if employee_ids else []
    alert_by_id: dict[int, Alert] = {alert.id: alert for alert in scoped_alerts}
    hr_alerts = list(
        db.scalars(
            select(Alert).where(
                Alert.status == "open",
                Alert.alert_type.in_(("exit", "bench")),
            )
        ).all()
    )
    candidate_ids = set(employee_ids)
    for code in employee_codes_for_ids:
        try:
            candidate_ids.add(int(code.strip()))
        except ValueError:
            continue
    for alert in hr_alerts:
        if alert.id in alert_by_id or not _is_visible_alert(alert):
            continue
        if org_level or (alert.employee_id in candidate_ids if alert.employee_id else False):
            alert_by_id[alert.id] = alert
            continue
        if alert.employee_id:
            emp_row = db.get(Employee, alert.employee_id)
            if emp_row and emp_row.employee_code:
                try:
                    if int((emp_row.employee_code or "").strip()) in candidate_ids:
                        alert_by_id[alert.id] = alert
                except ValueError:
                    pass
    alerts = list(alert_by_id.values())
    # Queue and requests: load all (queue is admin-level, no employee scoping needed;
    # filtering by 5763 Aspire IDs would also exceed SQL Server's 2100-param limit).
    # Exclude orphaned pending items whose linked request is already approved/rejected.
    queue_items = list(
        db.scalars(
            select(QueueItem)
            .outerjoin(
                LicenseRequest,
                (QueueItem.source_type == "request") & (QueueItem.source_id == LicenseRequest.id)
            )
            .where(QueueItem.status == "pending")
            .where(
                or_(
                    QueueItem.source_type != "request",
                    LicenseRequest.id.is_(None),
                    LicenseRequest.approval_stage.not_in(["approved", "rejected"]),
                )
            )
            .order_by(QueueItem.created_at.desc())
        ).all()
    )
    requests = list(
        db.scalars(
            select(LicenseRequest)
            .order_by(LicenseRequest.created_at.desc())
        ).all()
    )
    audits = list(
        db.scalars(
            select(AllocationAudit)
            .where(AllocationAudit.allocation_id.in_(allocation_ids))
            .order_by(AllocationAudit.changed_at)
        ).all()
    ) if allocation_ids else []

    account_ids = sorted({employee.account_id for employee in employees if employee.account_id is not None})
    project_ids = sorted({employee.project_id for employee in employees if employee.project_id is not None})
    gdl_ids = sorted({employee.gdl_id for employee in employees if employee.gdl_id is not None})

    try:
        accounts = list(
            db.scalars(select(Account).where(Account.id.in_(account_ids)).order_by(Account.name)).all()
        ) if account_ids else []
    except Exception:
        accounts = []
    try:
        gdls = list(
            db.scalars(select(GDL).where(GDL.id.in_(gdl_ids)).order_by(GDL.code)).all()
        ) if gdl_ids else []
    except Exception:
        gdls = []
    try:
        projects = list(
            db.scalars(select(Project).where(Project.id.in_(project_ids)).order_by(Project.name)).all()
        ) if project_ids else []
    except Exception:
        projects = []

    user_map = {}
    account_map = {account.id: account for account in accounts}
    gdl_map = {gdl.id: gdl for gdl in gdls}
    project_map = {project.id: project for project in projects}
    platform_map = {platform.id: platform for platform in platforms}
    employee_map = {employee.id: employee for employee in employees}

    employee_real_id_by_code: dict[str, int] = {}
    employee_codes = list({
        (getattr(employee, "employee_code", None) or "").strip()
        for employee in employees
        if getattr(employee, "employee_code", None)
    } - {""})
    if employee_codes:
        try:
            linked_rows = []
            for i in range(0, len(employee_codes), 1500):
                chunk = employee_codes[i:i + 1500]
                linked_rows.extend(db.scalars(select(Employee).where(Employee.employee_code.in_(chunk))).all())
            employee_real_id_by_code = {(row.employee_code or "").strip(): row.id for row in linked_rows if row.employee_code}
        except Exception:
            employee_real_id_by_code = {}
    for employee in employees:
        employee_code = (getattr(employee, "employee_code", None) or "").strip()
        real_id = employee_real_id_by_code.get(employee_code)
        if real_id is not None:
            employee_map[real_id] = employee

    # Build account owner name map for Aspire employees (staffid → full name)
    # Done once here to avoid per-employee Aspire queries
    aspire_owner_name_map: dict[str, str] = {}
    if is_aspire:
        owner_staffids = {
            getattr(emp, "_aspire_account_owner_staffid", "") or ""
            for emp in employees
        } - {""}  # remove empty strings
        if owner_staffids:
            try:
                adb = aspire_svc.get_aspire_session()
                from app.models.aspire import AspireEmployee as _AE
                owner_rows = adb.scalars(
                    select(_AE).where(_AE.emp_staffid.in_(list(owner_staffids)))
                ).all()
                aspire_owner_name_map = {(r.emp_staffid or "").strip(): r.full_name for r in owner_rows}
                adb.close()
            except Exception:
                pass  # non-fatal — acctOwner will just be empty

    allocation_by_employee: dict[int, list[LicenseAllocation]] = defaultdict(list)
    allocation_by_platform: dict[int, list[LicenseAllocation]] = defaultdict(list)
    for allocation in allocations:
        allocation_by_employee[allocation.employee_id].append(allocation)
        allocation_by_platform[allocation.platform_id].append(allocation)

    platform_pool_seats: dict[int, int] = {
        platform_id: count
        for platform_id, count in db.execute(
            select(
                LicenseAllocation.platform_id,
                func.count(func.distinct(LicenseAllocation.employee_id)),
            )
            .where(LicenseAllocation.revoked_date.is_(None))
            .group_by(LicenseAllocation.platform_id)
        ).all()
    }

    platform_records: list[PlatformUiRecord] = []
    snapshot_records: dict[str, list[PlatformSeatSnapshotPoint]] = defaultdict(list)
    for snapshot in seat_snapshots:
        snapshot_records[str(snapshot.platform_id)].append(
            PlatformSeatSnapshotPoint(date=_fmt_date(snapshot.snapshot_date), seats=snapshot.seat_count)
        )

    for platform in platforms:
        contract = sorted(
            platform.contracts,
            key=lambda item: item.effective_from or date.min,
            reverse=True,
        )[0] if platform.contracts else None
        platform_allocations = allocation_by_platform.get(platform.id, [])
        active_seats = len({
            alloc.employee_id
            for alloc in platform_allocations
            if _allocation_is_current(alloc)
        })
        contracted_seats = contract.contracted_seats if contract and contract.contracted_seats else 0
        platform_records.append(
            PlatformUiRecord(
                id=platform.id,
                name=platform.name,
                vendor=platform.vendor,
                cat=platform.category,
                agr=platform.agreement_type,
                type=platform.license_type,
                billing=platform.billing_period,
                currency=platform.currency,
                seatCost=float(contract.seat_cost or 0) if contract and contract.seat_cost is not None else 0,
                entCost=float(contract.enterprise_cost or 0) if contract and contract.enterprise_cost is not None else 0,
                entSeats=contracted_seats if platform.license_type == "enterprise" else 0,
                purchasedSeats=contracted_seats,
                alloc=(contract.allocation_method if contract and contract.allocation_method else "equal"),
                effectiveDate=_fmt_date(platform.effective_date),
                renewal=_fmt_date(platform.renewal_date),
                activeSeats=active_seats,
                poolActiveSeats=platform_pool_seats.get(platform.id, 0),
                inactiveDays=platform.inactivity_days,
                contractor="yes" if platform.contractor_allowed else "no",
                shared="yes" if platform.shared_allowed else "no",
                api="yes" if platform.api_available else "no",
                notes=platform.notes or "",
            )
        )

    employee_records: list[EmployeeUiRecord] = []
    allocation_history: dict[str, list[AllocationHistoryUiRecord]] = defaultdict(list)
    for employee in employees:
        account = account_map.get(employee.account_id)
        project = project_map.get(employee.project_id)
        gdl = gdl_map.get(employee.gdl_id) if employee.gdl_id else None
        account_owner = user_map.get(employee.account_owner_user_id or (account.owner_user_id if account else None))
        # For Aspire-backed views, prefer proxy names over local ID-based tables because
        # Aspire IDs can overlap unrelated LicenseIQ local IDs.
        if is_aspire:
            acct_name = getattr(employee, "_aspire_account_name", "") or (account.name if account else None) or ""
            proj_name = getattr(employee, "_aspire_project_name", "") or (project.name if project else None) or ""
            gdl_code = getattr(employee, "_aspire_du_code", "") or (gdl.code if gdl else None) or ""
        else:
            acct_name = (account.name if account else None) or getattr(employee, "_aspire_account_name", "") or ""
            proj_name = (project.name if project else None) or getattr(employee, "_aspire_project_name", "") or ""
            gdl_code = (gdl.code if gdl else None) or getattr(employee, "_aspire_du_code", "") or ""
        # Resolve account owner name: LicenseIQ user first, then Aspire staffid lookup
        owner_staffid_key = getattr(employee, "_aspire_account_owner_staffid", "") or ""
        acct_owner_name = (
            (account_owner.full_name if account_owner else None)
            or aspire_owner_name_map.get(owner_staffid_key, "")
            or owner_staffid_key  # fallback: show staffid if name not found
        )
        allocation_keys = {employee.id}
        employee_code = (getattr(employee, "employee_code", None) or "").strip()
        linked_real_id = employee_real_id_by_code.get(employee_code)
        if linked_real_id is not None:
            allocation_keys.add(linked_real_id)
        try:
            allocation_keys.add(int(employee_code))
        except ValueError:
            pass
        employee_allocations = sorted(
            {
                allocation.id: allocation
                for allocation_key in allocation_keys
                for allocation in allocation_by_employee.get(allocation_key, [])
            }.values(),
            key=lambda item: (item.effective_date or date.min, item.id),
        )
        licenses: list[LicenseUiRecord] = []
        for allocation in employee_allocations:
            platform = platform_map.get(allocation.platform_id)
            project_name = project_map.get(allocation.project_id).name if project_map.get(allocation.project_id) else proj_name
            pool_seats = platform_pool_seats.get(allocation.platform_id, 0) if platform else 0
            alloc_cost = money_float(
                resolve_allocation_monthly_cost(
                    allocation.monthly_cost,
                    platform,
                    pool_seats=pool_seats or None,
                )
            )
            licenses.append(
                LicenseUiRecord(
                    plat=platform.name if platform else "Unknown",
                    cost=alloc_cost,
                    type=(
                        "Enterprise"
                        if platform and platform.license_type == "enterprise"
                        else "Usage based"
                        if platform and platform.license_type == "usage_based"
                        else "Per user"
                    ),
                    last=_fmt_date((allocation.last_used_at.date() if allocation.last_used_at else allocation.effective_date)),
                    st=allocation.status,
                    isCurrent=_allocation_is_current(allocation),
                )
            )
            allocation_history[str(employee.id)].append(
                AllocationHistoryUiRecord(
                    date=_fmt_date(allocation.effective_date),
                    action="Assigned",
                    plat=platform.name if platform else "Unknown",
                    proj=project_name,
                    by="System",
                )
            )
        all_assignments = getattr(employee, "_all_assignments", None) or []
        employee_records.append(
            EmployeeUiRecord(
                id=str(employee.id),
                code=(getattr(employee, "employee_code", None) or "").strip(),
                name=employee.full_name,
                unit=employee.unit,
                proj=proj_name,
                proj_id=employee.project_id,
                acct=acct_name,
                acct_id=employee.account_id,
                acctOwner=acct_owner_name,
                gdl=gdl_code,
                status=employee.employment_status,
                lics=licenses,
                assignments=all_assignments,
                oracle_id=(getattr(employee, "_oracle_id", None) or "").strip(),
            )
        )

    allocation_id_map: dict[int, LicenseAllocation] = {allocation.id: allocation for allocation in allocations}
    for audit in audits:
        allocation = allocation_id_map.get(audit.allocation_id)
        if not allocation:
            continue
        employee = employee_map.get(allocation.employee_id)
        platform = platform_map.get(allocation.platform_id)
        project = project_map.get(allocation.project_id)
        if not employee:
            continue
        allocation_history[str(employee.id)].append(
            AllocationHistoryUiRecord(
                date=_fmt_date(audit.changed_at.date()),
                action=(audit.event_type or "Updated").replace("_", " ").title(),
                plat=platform.name if platform else "Unknown",
                proj=project.name if project else "",
                by=(user_map.get(audit.changed_by_user_id).full_name if audit.changed_by_user_id in user_map else audit.event_source),
            )
        )

    alert_employee_ids = {alert.employee_id for alert in alerts if alert.employee_id}
    missing_alert_emp_ids = alert_employee_ids - set(employee_map.keys())
    if missing_alert_emp_ids:
        missing_list = list(missing_alert_emp_ids)
        for i in range(0, len(missing_list), 2000):
            chunk = missing_list[i:i + 2000]
            for emp_row in db.scalars(select(Employee).where(Employee.id.in_(chunk))).all():
                employee_map[emp_row.id] = emp_row

    alert_records: list[AlertUiRecord] = []
    for alert in alerts:
        if not _is_visible_alert(alert):
            continue
        employee = employee_map.get(alert.employee_id) if alert.employee_id else None
        if employee:
            emp_code = (getattr(employee, "employee_code", None) or "").strip()
            emp_id = emp_code or str(employee.id)
            emp_name = employee.full_name
        elif alert.employee_id:
            emp_id = str(alert.employee_id)
            emp_name = None
        else:
            emp_id = ""
            emp_name = None
        alert_records.append(
            AlertUiRecord(
                empId=emp_id,
                empName=emp_name,
                type=alert.alert_type,
                pri=alert.priority,
                reason=alert.reason,
                detail=alert.detail or "",
            )
        )

    queue_records: list[QueueUiRecord] = []
    # Build a supplemental name map for queue employees not in scoped employee_map.
    # employee_id in queue items = Aspire staff ID (synthetic int from staffid string).
    # Look them up directly from Aspire by staffid.
    queue_employee_ids = {item.employee_id for item in queue_items if item.employee_id and item.employee_id not in employee_map}
    supplemental_emp_map: dict[int, str] = {}
    if queue_employee_ids:
        try:
            adb = aspire_svc.get_aspire_session()
            try:
                for eid in queue_employee_ids:
                    staffid_str = str(eid).strip()
                    asp_emp = aspire_svc.get_aspire_employee_by_staffid(adb, staffid_str)
                    if asp_emp and asp_emp.full_name:
                        supplemental_emp_map[eid] = asp_emp.full_name
            finally:
                adb.close()
        except Exception:
            pass

    for item in queue_items:
        employee = employee_map.get(item.employee_id) if item.employee_id else None
        emp_name = (employee.full_name if employee else None) or supplemental_emp_map.get(item.employee_id) or "Unknown"
        platform = platform_map.get(item.platform_id) if item.platform_id else None
        project = project_map.get(item.project_id) if item.project_id else None
        requested_by = user_map.get(item.requested_by_user_id) if item.requested_by_user_id else None
        queue_records.append(
            QueueUiRecord(
                id=item.id,
                source_id=item.source_id,
                emp=emp_name,
                emp_id=item.employee_id,
                plat=platform.name if platform else "Unknown",
                type=item.action_type,
                proj=project.name if project else "",
                by=requested_by.full_name if requested_by else (item.source_type.title() if item.source_type else "System"),
                date=_fmt_short_date(item.created_at.date()),
                cost=float(item.cost_snapshot_monthly or 0),
                status=item.status,
                manual=item.source_type != "aspire",
                approval_stage=getattr(item, "approval_stage", None),
            )
        )

    manual_alert_records: list[ManualAlertUiRecord] = []
    for request in requests:
        employee = employee_map.get(request.employee_id)
        platform = platform_map.get(request.platform_id)
        project = project_map.get(request.project_id)
        requested_by = user_map.get(request.requested_by_user_id) if request.requested_by_user_id else None
        platform_cost = (
            money_float(calculate_platform_monthly_unit_cost_for_platform(db, platform))
            if platform
            else 0
        )
        manual_alert_records.append(
            ManualAlertUiRecord(
                emp=employee.full_name if employee else "Unknown",
                plat=platform.name if platform else "Unknown",
                type=request.request_type,
                proj=project.name if project else "",
                by=requested_by.full_name if requested_by else "Self-approved",
                date=_fmt_short_date(request.effective_date or request.created_at.date()),
                cost=platform_cost,
                pri="medium",
            )
        )

    years = _dashboard_years(allocations)
    monthly_spend: dict[str, dict[str, list[float]]] = {
        str(year): {platform.name: [0.0] * 12 for platform in platforms} for year in years
    }
    monthly_project: dict[str, dict[str, list[float]]] = {str(year): {} for year in years}
    today_date = date.today()
    current_year = today_date.year
    current_month = today_date.month
    for allocation in allocations:
        platform = platform_map.get(allocation.platform_id)
        employee = employee_map.get(allocation.employee_id)
        project = project_map.get(allocation.project_id)
        project_name = (
            (getattr(employee, "_aspire_project_name", "") if employee else "")
            or (project.name if project else "")
        )
        if not platform or not project_name:
            continue
        pool_seats = platform_pool_seats.get(allocation.platform_id, 0)
        amount = money_float(
            resolve_allocation_monthly_cost(
                allocation.monthly_cost,
                platform,
                pool_seats=pool_seats or None,
            )
        )
        is_current = _allocation_is_current(allocation)
        for year in years:
            for month in MONTHS:
                # For the current month only count non-revoked allocations so the
                # series matches the monthly-spend KPI (which sums currentLicenses).
                if year == current_year and month == current_month and not is_current:
                    continue
                if _allocation_active_in_month(allocation, year, month):
                    monthly_spend[str(year)][platform.name][month - 1] += amount
                    if project_name not in monthly_project[str(year)]:
                        monthly_project[str(year)][project_name] = [0.0] * 12
                    monthly_project[str(year)][project_name][month - 1] += amount

    project_meta: dict[str, ProjectMetaUiRecord] = {
        project.name: ProjectMetaUiRecord(
            acct=account_map.get(project.account_id).name if account_map.get(project.account_id) else "",
            gdl=gdl_map.get(project.gdl_id).display_name if project.gdl_id and gdl_map.get(project.gdl_id) else "",
        )
        for project in projects
    }
    # For Aspire employees the LicenseIQ projects table is empty, so project_meta above has no
    # entries.  Build supplementary entries directly from the proxy fields on the employee records.
    for emp in employees:
        proj_name = getattr(emp, "_aspire_project_name", "") or ""
        acct_name = getattr(emp, "_aspire_account_name", "") or ""
        gdl_code  = getattr(emp, "_aspire_du_code", "") or ""
        if proj_name and proj_name not in project_meta:
            project_meta[proj_name] = ProjectMetaUiRecord(acct=acct_name, gdl=gdl_code)

    if is_aspire:
        account_names = sorted({
            (getattr(employee, "_aspire_account_name", "") or "").strip()
            for employee in employees
            if (getattr(employee, "_aspire_account_name", "") or "").strip()
        })
        project_records = sorted(
            {
                ((getattr(employee, "project_id", None), getattr(employee, "_aspire_project_name", "") or ""))
                for employee in employees
                if (getattr(employee, "_aspire_project_name", "") or "").strip()
            },
            key=lambda item: item[1],
        )
        gdl_codes = sorted({
            (getattr(employee, "_aspire_du_code", "") or "").strip()
            for employee in employees
            if (getattr(employee, "_aspire_du_code", "") or "").strip()
        })
    else:
        account_names = sorted({
            ((account_map.get(employee.account_id).name if account_map.get(employee.account_id) else None)
             or getattr(employee, "_aspire_account_name", "")
             or "").strip()
            for employee in employees
            if (((account_map.get(employee.account_id).name if account_map.get(employee.account_id) else None)
                 or getattr(employee, "_aspire_account_name", "")
                 or "").strip())
        })
        project_records = [(project.id, project.name) for project in projects]
        gdl_codes = [gdl.code for gdl in gdls]

    return DashboardBootstrapResponse(
        platforms=platform_records,
        employees=employee_records,
        alerts=alert_records,
        manual_alerts=manual_alert_records,
        queue=queue_records,
        seat_snapshots=dict(snapshot_records),
        monthly_spend=monthly_spend,
        monthly_project=monthly_project,
        alloc_hist={key: sorted(value, key=lambda item: item.date, reverse=True) for key, value in allocation_history.items()},
        project_meta=project_meta,
        units=sorted({employee.unit for employee in employees}),
        accounts=account_names,
        projects=[{"id": project_id, "name": project_name} for project_id, project_name in project_records],
        gdls=gdl_codes,
    )
