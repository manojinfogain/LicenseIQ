from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.error_utils import handle_database_error, handle_unexpected_error
from app.core.aspire_database import get_aspire_db
from app.models.aspire import AspireEmployee
from app.models.license import Alert, LicenseAllocation, LicenseRequest
from app.models.organization import Employee, Project
from app.models.platform import Platform
from app.schemas.alert import AlertRead
from app.schemas.dashboard import ManualAlertUiRecord
from app.services.pricing import calculate_platform_monthly_unit_cost
from app.services import aspire_events
from app.services.phase1_integration import get_open_alerts_phase1


router = APIRouter()

def _fmt_date(d) -> str:
    if hasattr(d, "strftime"):
        return d.strftime("%d/%m/%Y")
    return str(d)


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


@router.get("", response_model=list[AlertRead])
def list_alerts(db: Session = Depends(get_db), aspire_db: Session = Depends(get_aspire_db)) -> list[AlertRead]:
    try:
        # Get alerts using Phase 1 SP if enabled, ORM fallback
        alert_dicts = get_open_alerts_phase1(db)
        
        # Convert dicts back to ORM objects for processing
        alerts = []
        for alert_dict in alert_dicts:
            alert = db.get(Alert, alert_dict["id"])
            if alert:
                alerts.append(alert)
        
        # Post-processing: filter by allocation ownership and visibility
        emp_ids = {a.employee_id for a in alerts if a.employee_id}
        emp_code_map = {}
        emp_name_map = {}
        if emp_ids:
            rows = db.scalars(select(Employee).where(Employee.id.in_(emp_ids))).all()
            emp_code_map = {e.id: e.employee_code for e in rows}
            emp_name_map = {e.id: e.full_name for e in rows}

        # Build a map EMP_STAFFID -> Emp_NewID for display purposes
        staffid_to_new_id: dict[str, str] = {}
        all_staffids = [code for code in emp_code_map.values() if code]
        if all_staffids:
            aspire_rows = aspire_db.execute(
                select(AspireEmployee.emp_staffid, AspireEmployee.emp_new_id).where(
                    AspireEmployee.emp_staffid.in_(all_staffids)
                )
            ).all()
            staffid_to_new_id = {
                r.emp_staffid: (r.emp_new_id or "").strip()
                for r in aspire_rows
                if (r.emp_new_id or "").strip()
            }

        candidate_allocation_ids = set(emp_ids)
        for employee_code in emp_code_map.values():
            try:
                candidate_allocation_ids.add(int((employee_code or "").strip()))
            except ValueError:
                continue
        for alert in alerts:
            if alert.employee_id:
                candidate_allocation_ids.add(alert.employee_id)

        active_allocation_owner_ids = set()
        any_allocation_owner_ids = set()
        if candidate_allocation_ids:
            active_allocation_owner_ids = set(
                db.scalars(
                    select(LicenseAllocation.employee_id).where(
                        LicenseAllocation.employee_id.in_(candidate_allocation_ids),
                        LicenseAllocation.revoked_date.is_(None),
                    )
                ).all()
            )
            # For exit alerts: also include employees who had any allocation (even revoked)
            any_allocation_owner_ids = set(
                db.scalars(
                    select(LicenseAllocation.employee_id).where(
                        LicenseAllocation.employee_id.in_(candidate_allocation_ids),
                    )
                ).all()
            )

        result = []
        for a in alerts:
            employee_code = emp_code_map.get(a.employee_id) if a.employee_id else None
            employee_name = emp_name_map.get(a.employee_id) if a.employee_id else None
            synthetic_id = None
            try:
                synthetic_id = int((employee_code or "").strip())
            except ValueError:
                synthetic_id = None
            # Exit alerts: show if employee ever had any allocation (even if now revoked)
            # Other alerts: require an active (non-revoked) allocation
            if a.alert_type == "exit":
                allowed_ids = any_allocation_owner_ids
            else:
                allowed_ids = active_allocation_owner_ids
            if a.employee_id not in allowed_ids and synthetic_id not in allowed_ids:
                continue
            if not _is_visible_alert(a):
                continue
            d = AlertRead.model_validate(a)
            display_code = staffid_to_new_id.get(employee_code or "", "") or employee_code
            d.employee_code = display_code
            d.employee_name = employee_name
            result.append(d)
        return result
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "list alerts")
    except Exception as exc:
        handle_unexpected_error(db, exc, "list alerts")


@router.get("/manual", response_model=list[ManualAlertUiRecord])
def list_manual_alerts(db: Session = Depends(get_db)) -> list[ManualAlertUiRecord]:
    """Return pending license requests formatted as manual alert cards (same shape as bootstrap)."""
    try:
        requests = list(
            db.scalars(
                select(LicenseRequest)
                .where(LicenseRequest.approval_status.in_(["submitted", "self_approved"]))
                .order_by(LicenseRequest.created_at.desc())
            ).all()
        )

        employee_ids = {r.employee_id for r in requests}
        platform_ids = {r.platform_id for r in requests}
        project_ids  = {r.project_id  for r in requests}

        employee_map = {e.id: e for e in db.scalars(select(Employee).where(Employee.id.in_(employee_ids))).all()} if employee_ids else {}
        platform_map = {p.id: p for p in db.scalars(select(Platform).where(Platform.id.in_(platform_ids))).all()} if platform_ids else {}
        project_map  = {p.id: p for p in db.scalars(select(Project).where(Project.id.in_(project_ids))).all()} if project_ids else {}

        records: list[ManualAlertUiRecord] = []
        for r in requests:
            platform = platform_map.get(r.platform_id)
            project  = project_map.get(r.project_id)
            employee = employee_map.get(r.employee_id)
            platform_cost = float(calculate_platform_monthly_unit_cost(platform)) if platform else 0.0
            effective = r.effective_date or r.created_at.date()
            records.append(ManualAlertUiRecord(
                emp=employee.full_name if employee else "Unknown",
                plat=platform.name if platform else "Unknown",
                type=r.request_type,
                proj=project.name if project else "",
                by="Self-approved",
                date=_fmt_date(effective),
                cost=platform_cost,
                pri="medium",
            ))
        return records
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "list manual alerts")
    except Exception as exc:
        handle_unexpected_error(db, exc, "list manual alerts")


@router.post("/aspire-sync")
def aspire_sync(
    db: Session = Depends(get_db),
    lookback_days: int = Query(default=7, ge=1, le=90, description="How many days back to look for Aspire events"),
    dry_run: bool = Query(default=False, description="Preview what would be created without writing to DB"),
):
    """
    Pull recent events from Aspire HRMS and create Smart Alerts for
    employees who still hold active licenses.

    Detects:
    - Exit / resignation (SEP_ResignationDetails)
    - Project release / change (RPT_FeedbackOnRelease)
    - Bench / non-billable (RPT_PROJECT_ASSIGNMENT BILLABLE='N')

    Returns a summary of how many alerts were created per event type.
    """
    try:
        result = aspire_events.sync_aspire_events(
            db,
            lookback_days=lookback_days,
            dry_run=dry_run,
        )
        return result
    except Exception as exc:
        handle_unexpected_error(db, exc, "aspire-sync")
