"""
Aspire HRMS Event Sync Service

Detects employee status change events from Aspire and creates Smart Alerts:
  - EXIT   : SEP_ResignationDetails — employee resigned / last working date reached
  - BENCH  : RPT_PROJECT_ASSIGNMENT — employee is non-billable (BILLABLE='N') with no active project
  - PROJECT_CHANGE : RPT_FeedbackOnRelease — employee released from a project recently
  - TRANSFER: PIM_EMPLOYEE_TRANSFER — employee transferred to different role/location

Only creates an alert when:
  1. The Aspire event is NEW (within look-back window or since last sync)
  2. The employee holds at least one active license in LicenseIQ
  3. No open alert of the same type already exists for that employee
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.aspire_database import AspireSessionLocal
from app.models.license import Alert, LicenseAllocation
from app.models.organization import Employee
from app.models.platform import Platform

log = logging.getLogger(__name__)

# ── helpers ──────────────────────────────────────────────────────────────────

def _get_aspire_db():
    return AspireSessionLocal()


def _employee_id_for_staffid(db: Session, staffid: str) -> int | None:
    """Resolve Aspire staffid to a real employees.id for alert inserts."""
    cleaned = staffid.strip()
    emp = db.scalar(
        sa.select(Employee).where(Employee.employee_code == cleaned)
    )
    return emp.id if emp else None


def _resolve_alert_employee_id(db: Session, staffid: str) -> int | None:
    """Prefer the id used on license allocations (often synthetic Aspire staffid)."""
    cleaned = staffid.strip()
    if not cleaned:
        return None
    candidate_ids: list[int] = []
    real_id = _employee_id_for_staffid(db, cleaned)
    if real_id is not None:
        candidate_ids.append(real_id)
    try:
        candidate_ids.append(int(cleaned))
    except ValueError:
        pass
    seen: set[int] = set()
    for employee_id in candidate_ids:
        if employee_id in seen:
            continue
        seen.add(employee_id)
        if _active_allocations_for_staffid(db, cleaned, employee_id):
            return employee_id
    return candidate_ids[0] if candidate_ids else None


def _active_allocations_for_staffid(db: Session, staffid: str, employee_id: int | None) -> list[LicenseAllocation]:
    """Return active allocations for both real employee PK and synthetic staffid keys."""
    employee_ids: set[int] = set()
    if employee_id is not None:
        employee_ids.add(employee_id)
    try:
        employee_ids.add(int(staffid.strip()))
    except ValueError:
        pass
    if not employee_ids:
        return []
    return list(
        db.scalars(
            sa.select(LicenseAllocation).where(
                LicenseAllocation.employee_id.in_(employee_ids),
                LicenseAllocation.revoked_date.is_(None),
            )
        ).all()
    )


def _open_alert_exists(
    db: Session,
    employee_id: int,
    alert_type: str,
    *,
    staffid: str | None = None,
) -> bool:
    """True if there is already an open alert of this type for the employee."""
    employee_ids = {employee_id}
    if staffid:
        try:
            employee_ids.add(int(staffid.strip()))
        except ValueError:
            pass
        linked = _employee_id_for_staffid(db, staffid)
        if linked is not None:
            employee_ids.add(linked)
    return db.scalar(
        sa.select(Alert.id).where(
            Alert.employee_id.in_(employee_ids),
            Alert.alert_type == alert_type,
            Alert.status == "open",
        )
    ) is not None


def _platform_name(db: Session, platform_id: int) -> str:
    p = db.get(Platform, platform_id)
    return p.name if p else str(platform_id)


def _fmt_date_for_display(d: date | None) -> str:
    """Format date as DD/MM/YYYY for display in alerts."""
    if not d:
        return "unknown date"
    return d.strftime("%d/%m/%Y")


def _create_alert(
    db: Session,
    *,
    employee_id: int,
    platform_id: int | None,
    alert_type: str,
    priority: str,
    reason: str,
    detail: str,
) -> Alert:
    alert = Alert(
        employee_id=employee_id,
        platform_id=platform_id,
        alert_type=alert_type,
        priority=priority,
        source_system="aspire",
        reason=reason,
        detail=detail,
        status="open",
    )
    db.add(alert)
    return alert


def _fetch_aspire_rows(adb, proc_sql: str, fallback_sql: str, params: dict) -> list:
    try:
        return adb.execute(sa.text(proc_sql), params).fetchall()
    except sa.exc.DBAPIError as exc:
        log.warning("Falling back to inline Aspire query; stored procedure unavailable: %s", exc)
        return adb.execute(sa.text(fallback_sql), params).fetchall()


# ── event detectors ───────────────────────────────────────────────────────────

def _sync_exit_events(
    db: Session,
    adb,
    since: datetime,
    dry_run: bool,
) -> list[dict]:
    """
    Detect exits: query SEP_ResignationDetails for employees whose
    LastWorkingDate is due within the next 15 days OR whose resignation was
    added/modified since the last sync.

    Employees who reverted (ResignationRevertDate IS NOT NULL) are skipped.
    """
    future = datetime.utcnow() + timedelta(days=15)
    rows = _fetch_aspire_rows(
        adb,
        "EXEC dbo.usp_GetAspireExitEvents @since=:since, @future=:future",
        """
            SELECT
                RTRIM(EmpId)          AS EmpId,
                ResignationDate,
                LastWorkingDate,
                ExitType,
                ResignationReason,
                ResignedStatus,
                ResignationRevertDate,
                Project,
                Account
            FROM [DBO].[SEP_ResignationDetails]
            WHERE IsActive  = 1
              AND IsDeleted = 0
              AND ResignationRevertDate IS NULL
              AND (
                  (LastWorkingDate >= :since AND LastWorkingDate <= :future)
                  OR (AddedOn >= :since)
                  OR (ModifiedOn >= :since)
              )
        """,
        {"since": since, "future": future},
    )

    created = []
    for row in rows:
        staff_id = (row.EmpId or "").strip()
        if not staff_id:
            continue


        employee_id = _resolve_alert_employee_id(db, staff_id)
        if not employee_id:
            log.debug("EXIT event — staffid %s not found in LicenseIQ", staff_id)
            continue

        allocations = _active_allocations_for_staffid(db, staff_id, employee_id)
        if not allocations:
            log.debug("EXIT event — staffid %s has no active licenses", staff_id)
            continue

        if _open_alert_exists(db, employee_id, "exit", staffid=staff_id):
            continue

        lwd = row.LastWorkingDate.date() if row.LastWorkingDate else None
        reason = f"Exit event from Aspire — LWD {_fmt_date_for_display(lwd)}"
        detail = (
            f"Employee has resigned. Last working date: {_fmt_date_for_display(lwd)}. "
            f"Reason: {row.ResignationReason or 'Not provided'}. "
            f"Project: {row.Project or '-'}  Account: {row.Account or '-'}. "
            f"All licenses must be revoked immediately."
        )

        if not dry_run:
            _create_alert(
                db,
                employee_id=employee_id,
                platform_id=None,
                alert_type="exit",
                priority="high",
                reason=reason,
                detail=detail,
            )

        created.append({"type": "exit", "staffid": staff_id, "reason": reason})

    return created


def _sync_project_release_events(
    db: Session,
    adb,
    since: datetime,
    dry_run: bool,
) -> list[dict]:
    """
    Detect project change events: query RPT_FeedbackOnRelease for records
    where AllocationEndDate is within the look-back window.
    """
    today = datetime.utcnow()
    rows = _fetch_aspire_rows(
        adb,
        "EXEC dbo.usp_GetAspireProjectReleaseEvents @since=:since, @today=:today",
        """
            SELECT
                RTRIM(EmployeeId) AS EmployeeId,
                AccountId,
                ProjectId,
                ReleaseReason,
                AllocationEndDate,
                FeedbackGivenOn
            FROM [DBO].[RPT_FeedbackOnRelease]
            WHERE IsActive = 1
              AND AllocationEndDate >= :since
              AND AllocationEndDate <= :today
        """,
        {"since": since, "today": today},
    )

    # Look up release reasons
    reason_map: dict[int, str] = {}
    try:
        reason_rows = _fetch_aspire_rows(
            adb,
            "EXEC dbo.usp_GetAspireReleaseReasons",
            "SELECT Id, ReleaseReason FROM [DBO].[RPT_Release_Reason] WHERE IsActive=1",
            {},
        )
        reason_map = {r.Id: r.ReleaseReason for r in reason_rows}
    except Exception:
        pass

    created = []
    for row in rows:
        staff_id = (row.EmployeeId or "").strip()
        if not staff_id:
            continue

        employee_id = _resolve_alert_employee_id(db, staff_id)
        if not employee_id:
            continue

        allocations = _active_allocations_for_staffid(db, staff_id, employee_id)
        if not allocations:
            continue

        if _open_alert_exists(db, employee_id, "project_change", staffid=staff_id):
            continue

        release_reason_text = reason_map.get(row.ReleaseReason, "Unknown") if row.ReleaseReason else "Not specified"
        end_date = row.AllocationEndDate.date() if row.AllocationEndDate else None
        reason = f"Project release from Aspire — {_fmt_date_for_display(end_date)}"
        detail = (
            f"Employee was released from project (AccountId: {row.AccountId}, ProjectId: {row.ProjectId}). "
            f"Release reason: {release_reason_text}. "
            f"Allocation end date: {_fmt_date_for_display(end_date)}. "
            f"License cost reallocation required."
        )

        if not dry_run:
            _create_alert(
                db,
                employee_id=employee_id,
                platform_id=None,
                alert_type="project_change",
                priority="medium",
                reason=reason,
                detail=detail,
            )

        created.append({"type": "project_change", "staffid": staff_id, "reason": reason})

    return created


def _sync_bench_events(
    db: Session,
    adb,
    since: datetime,
    dry_run: bool,
) -> list[dict]:
    """
    Detect Corporate Pool events: employees who are active in Aspire and are
    currently assigned to the "Corporate Pool (Corp Pool)" project, with the
    assignment modified within the look-back window.
    """
    today = datetime.utcnow()
    rows = _fetch_aspire_rows(
        adb,
        "EXEC dbo.usp_GetAspireBenchEvents @since=:since, @today=:today",
        """
            SELECT DISTINCT
                RTRIM(pa.ASG_EMP_STAFFID) AS EmpId,
                p.PROJECT_NAME,
                pa.BILLABLE,
                pa.PROJECT_STARTDATE,
                pa.PROJECT_ENDDATE,
                pa.ASG_TIMESTAMP
            FROM [DBO].[RPT_PROJECT_ASSIGNMENT] pa
            JOIN [DBO].[ERM_EMPLOYEE_MASTER] e
                ON RTRIM(e.EMP_STAFFID) = RTRIM(pa.ASG_EMP_STAFFID)
            JOIN [DBO].[RPT_PROJECT_MASTER] p
                ON pa.ASG_PROJECT_ID = p.PROJECT_ID
            WHERE RTRIM(e.EMP_ISACTIVE) = '1'
              AND (p.PROJECT_NAME LIKE '%Corporate Pool%' OR p.PROJECT_NAME LIKE '%Corp Pool%')
              AND pa.ASG_TIMESTAMP >= :since
              AND (pa.PROJECT_ENDDATE IS NULL OR pa.PROJECT_ENDDATE >= :today)
        """,
        {"since": since, "today": today},
    )

    created = []
    for row in rows:
        staff_id = (row.EmpId or "").strip()
        if not staff_id:
            continue

        employee_id = _resolve_alert_employee_id(db, staff_id)
        if not employee_id:
            continue

        allocations = _active_allocations_for_staffid(db, staff_id, employee_id)
        if not allocations:
            continue

        if _open_alert_exists(db, employee_id, "bench", staffid=staff_id):
            continue

        reason = f"Corporate Pool — {(row.PROJECT_NAME or '').strip()}"
        start_date = row.PROJECT_STARTDATE.date() if hasattr(row.PROJECT_STARTDATE, 'date') else row.PROJECT_STARTDATE
        end_date = row.PROJECT_ENDDATE.date() if hasattr(row.PROJECT_ENDDATE, 'date') else row.PROJECT_ENDDATE
        detail = (
            f"Employee is assigned to Corporate Pool ({(row.PROJECT_NAME or '').strip()}). "
            f"Assignment start: {_fmt_date_for_display(start_date)}, end: {_fmt_date_for_display(end_date)}. "
            f"Employee is in Corporate Pool — all licenses should be reviewed for revocation."
        )

        if not dry_run:
            _create_alert(
                db,
                employee_id=employee_id,
                platform_id=None,
                alert_type="bench",
                priority="high",
                reason=reason,
                detail=detail,
            )

        created.append({"type": "bench", "staffid": staff_id, "reason": reason})

    return created


# ── public API ────────────────────────────────────────────────────────────────

def sync_aspire_events(
    db: Session,
    *,
    lookback_days: int = 7,
    dry_run: bool = False,
) -> dict:
    """
    Main entry point.  Queries Aspire for recent exit / project-change / bench
    events and creates open Alert records in LicenseIQ for employees who still
    hold active licenses.

    Args:
        db:            LicenseIQ database session.
        lookback_days: How far back to look for events (default 7 days).
        dry_run:       If True, detect events but do NOT write any alerts.

    Returns dict with counts and per-type detail.
    """
    since = datetime.utcnow() - timedelta(days=lookback_days)
    results: dict[str, list[dict]] = {
        "exit": [],
        "project_change": [],
        "bench": [],
    }

    adb = _get_aspire_db()
    try:
        results["exit"] = _sync_exit_events(db, adb, since, dry_run)
        results["project_change"] = _sync_project_release_events(db, adb, since, dry_run)
        results["bench"] = _sync_bench_events(db, adb, since, dry_run)
    finally:
        adb.close()

    if not dry_run:
        db.commit()

    summary = {
        "lookback_days": lookback_days,
        "dry_run": dry_run,
        "synced_at": datetime.utcnow().isoformat(),
        "total_alerts_created": sum(len(v) for v in results.values()),
        "exit": len(results["exit"]),
        "project_change": len(results["project_change"]),
        "bench": len(results["bench"]),
        "events": results,
    }
    log.info(
        "Aspire event sync complete: %d exit, %d project_change, %d bench alerts created",
        summary["exit"], summary["project_change"], summary["bench"],
    )
    return summary
