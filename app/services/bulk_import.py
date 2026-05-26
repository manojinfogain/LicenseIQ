from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.query_helpers import (
    find_active_allocation_id,
    find_pending_queue_item_id,
    find_pending_request_id,
)
from app.core.aspire_database import AspireSessionLocal
from app.models.aspire import AspireAccount, AspireEmployee, AspireProject, AspireProjectAssignment
from app.models.license import QueueItem
from app.models.organization import Account, Employee, Project
from app.models.platform import Platform
from app.services.license_execution import create_assignment_allocation
from app.services.pricing import calculate_platform_monthly_unit_cost_for_platform


logger = logging.getLogger(__name__)


HEADER_ALIASES = {
    "employee_name": {"employee name", "employee_name", "name", "user name", "user_name", "username"},
    "staff_id": {"staff_id", "staff id", "staffid", "emp_staffid", "emp_staff_id"},
    "emp_new_id": {"emp_newid", "emp_new_id", "emp new id", "emp_new id"},
    "email": {"email", "email id", "email_id", "emp_mailid", "mailid"},
    "platform_name": {"platform name", "platform_name", "platform", "license"},
}

PLATFORM_ALIASES = {
    "openai": ["Open AI Platform", "ChatGPT"],
    "open ai": ["Open AI Platform", "ChatGPT"],
    "open ai platform": ["Open AI Platform"],
    "chatgpt": ["ChatGPT"],
    "claude": ["Claude AI"],
    "claude ai": ["Claude AI"],
    "docker": ["Docker Hub"],
    "github copilot": ["Github Copilot"],
    "cursor": ["Cursor AI"],
    "cursor ai": ["Cursor AI"],
    "pinecone": ["PineCone AI"],
    "pinecone ai": ["PineCone AI"],
    "langwatch": ["Langwatch AI"],
    "langwatch ai": ["Langwatch AI"],
}


@dataclass
class ImportRowResult:
    row_number: int
    status: str
    employee_name: str | None
    staff_id: str | None
    emp_new_id: str | None
    email: str | None
    platform_name: str | None
    message: str


@dataclass
class ImportSummary:
    total_rows: int
    inserted_count: int
    skipped_duplicate_count: int
    exception_count: int
    failed_count: int
    has_errors: bool
    error_row_numbers: list[int]
    summary_message: str
    accepted_platform_names: list[str]
    row_results: list[ImportRowResult]


def _normalize_header(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_email(value: str | None) -> str | None:
    cleaned = _normalize_text(value)
    return cleaned.lower() if cleaned else None


def _normalize_platform_name(value: str | None) -> str | None:
    cleaned = _normalize_text(value)
    if not cleaned:
        return None
    return cleaned


def _resolve_platform(platform_by_name: dict[str, Platform], platform_name: str | None) -> Platform | None:
    if not platform_name:
        return None

    exact_match = platform_by_name.get(platform_name.lower())
    if exact_match:
        return exact_match

    for candidate in PLATFORM_ALIASES.get(platform_name.lower(), []):
        resolved = platform_by_name.get(candidate.lower())
        if resolved:
            return resolved

    return None


def _canonicalize_row(row: dict[str, str]) -> dict[str, str | None]:
    normalized = {_normalize_header(key): value for key, value in row.items()}
    mapped: dict[str, str | None] = {
        "employee_name": None,
        "staff_id": None,
        "emp_new_id": None,
        "email": None,
        "platform_name": None,
    }
    for canonical, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                mapped[canonical] = normalized[alias]
                break

    mapped["employee_name"] = _normalize_text(mapped["employee_name"])
    mapped["staff_id"] = _normalize_text(mapped["staff_id"])
    mapped["emp_new_id"] = _normalize_text(mapped["emp_new_id"])
    mapped["email"] = _normalize_email(mapped["email"])
    mapped["platform_name"] = _normalize_platform_name(mapped["platform_name"])
    return mapped


def _row_context(row_number: int, row: dict[str, str | None]) -> str:
    return (
        f"row={row_number}, employee_name={row['employee_name']!r}, staff_id={row['staff_id']!r}, "
        f"emp_new_id={row['emp_new_id']!r}, email={row['email']!r}, platform_name={row['platform_name']!r}"
    )


def _log_row_issue(level: str, message: str, row_number: int, row: dict[str, str | None], exc: Exception | None = None) -> None:
    log_message = f"[BULK_IMPORT] {message} | {_row_context(row_number, row)}"
    if level == "error":
        logger.error(log_message, exc_info=exc)
    elif level == "warning":
        logger.warning(log_message)
    else:
        logger.info(log_message)


def _resolve_aspire_employee_with_scope(staff_id: str) -> dict | None:
    """Fetch AspireEmployee with project assignments, projects, and accounts. Returns dict with extracted data."""
    with AspireSessionLocal() as aspire_db:
        employee = aspire_db.scalars(
            select(AspireEmployee)
            .options(
                selectinload(AspireEmployee.project_assignments)
                .selectinload(AspireProjectAssignment.project)
                .selectinload(AspireProject.account)
            )
            .where(func.rtrim(AspireEmployee.emp_staffid) == staff_id)
        ).first()
        if not employee:
            return None
        
        # Extract data while session is open to avoid lazy-load issues after session closes
        assignments_data = []
        for a in (employee.project_assignments or []):
            proj = a.project
            acc = proj.account if proj else None
            assignments_data.append({
                "project_id": proj.project_id if proj else None,
                "project_name": (proj.project_name or "").strip() if proj else None,
                "account_id": acc.account_id if acc else None,
                "account_name": (acc.account_name or "").strip() if acc else None,
                "project_enddate": proj.prj_enddate if proj else None,
            })
        
        return {
            "emp_staffid": (employee.emp_staffid or "").strip(),
            "full_name": employee.full_name or "",
            "is_active": employee.is_active,
            "assignments": assignments_data,
        }


def _get_or_create_local_account(db: Session, account_name: str | None) -> Account | None:
    """Find a local Account by name (case-insensitive), creating it if not found."""
    if not account_name:
        return None
    name = account_name.strip()
    account = db.scalars(select(Account).where(func.lower(Account.name) == name.lower())).first()
    if not account:
        account = Account(name=name, status="active")
        db.add(account)
        db.flush()
        logger.info(f"[BULK_IMPORT] Auto-created local Account: {name!r}")
    return account


def _get_or_create_local_project(db: Session, project_name: str | None, account_id: int) -> Project | None:
    """Find a local Project by name (case-insensitive), creating it if not found."""
    if not project_name:
        return None
    name = project_name.strip()
    project = db.scalars(select(Project).where(func.lower(Project.name) == name.lower())).first()
    if not project:
        project = Project(name=name, account_id=account_id, status="active")
        db.add(project)
        db.flush()
        logger.info(f"[BULK_IMPORT] Auto-created local Project: {name!r} (account_id={account_id})")
    return project


def _auto_create_local_employee(
    db: Session,
    aspire_data: dict,
) -> tuple[Employee | None, str | None]:
    """Create a local Employee record from Aspire data dict. Returns (employee, error_message)."""
    staff_id = aspire_data.get("emp_staffid", "").strip()
    full_name = aspire_data.get("full_name", "")
    is_active = aspire_data.get("is_active", False)
    assignments = aspire_data.get("assignments", [])

    # Pick primary assignment: sort by enddate descending (most recent first)
    assignments_sorted = sorted(assignments, key=lambda a: a.get("project_enddate") or datetime.max, reverse=True)

    primary = None
    for a in assignments_sorted:
        if a.get("account_name"):
            primary = a
            break
    if not primary:
        for a in assignments_sorted:
            if a.get("project_name"):
                primary = a
                break

    if not primary:
        return None, f"Employee (StaffID {staff_id}) has no project assignment in Aspire — cannot determine scope."

    project_name = primary.get("project_name", "").strip()
    account_name = primary.get("account_name", "").strip()

    if not account_name:
        return None, f"Employee (StaffID {staff_id}) Aspire project has no account — cannot determine scope."

    local_account = _get_or_create_local_account(db, account_name)
    if not local_account:
        return None, f"Could not resolve local account for {account_name!r}."

    local_project = _get_or_create_local_project(db, project_name, local_account.id)
    if not local_project:
        return None, f"Could not resolve local project for {project_name!r}."

    unit = project_name or account_name or "Unassigned"
    employment_status = "active" if is_active else "inactive"

    # Truncate values to fit database column lengths
    employee_code_truncated = (staff_id or "")[:50]  # String(50)
    full_name_truncated = (full_name or "")[:150]    # String(150)
    unit_truncated = (unit or "")[:100]              # String(100)

    new_employee = Employee(
        employee_code=employee_code_truncated,
        full_name=full_name_truncated,
        unit=unit_truncated,
        employment_status=employment_status,
        account_id=local_account.id,
        project_id=local_project.id,
    )
    db.add(new_employee)
    db.flush()
    logger.info(
        f"[BULK_IMPORT] Auto-created local Employee from Aspire: "
        f"employee_code={staff_id!r}, name={full_name!r}, "
        f"project={project_name!r}, account={account_name!r}"
    )
    return new_employee, None


def _resolve_local_employee(
    db: Session, row: dict[str, str | None]
) -> tuple[Employee | None, str | None]:
    """Resolve or auto-create a local Employee from CSV row. Returns (employee, error_message)."""
    staff_id = (row.get("staff_id") or "").strip()
    if not staff_id:
        return None, "Missing StaffID."

    # Step 1: Already in local DB?
    existing = db.scalars(select(Employee).where(Employee.employee_code == staff_id)).first()
    if existing:
        return existing, None

    # Step 2: Look up Aspire and auto-create
    aspire_data = _resolve_aspire_employee_with_scope(staff_id)
    if not aspire_data:
        return None, f"Employee not found in Aspire (StaffID {staff_id})."

    return _auto_create_local_employee(db, aspire_data)


def parse_csv_rows(csv_bytes: bytes) -> list[dict[str, str | None]]:
    decoded = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise ValueError("CSV file is missing header row.")

    normalized_headers = {_normalize_header(field) for field in reader.fieldnames if field}
    if not normalized_headers.intersection(HEADER_ALIASES["staff_id"]):
        raise ValueError("CSV file must include a StaffID column.")
    if not normalized_headers.intersection(HEADER_ALIASES["platform_name"]):
        raise ValueError("CSV file must include a Platform column.")

    rows: list[dict[str, str | None]] = []
    for row in reader:
        rows.append(_canonicalize_row(row))
    return rows


def _format_platform_list(platforms: list[Platform]) -> str:
    return ", ".join(sorted(platform.name for platform in platforms))


def run_bulk_license_import(
    db: Session,
    *,
    csv_rows: list[dict[str, str | None]],
    requested_by_user_id: int,
    effective_date: date | None,
    dry_run: bool,
) -> ImportSummary:
    platforms = db.scalars(select(Platform).options(selectinload(Platform.contracts))).all()
    platform_by_name = {platform.name.strip().lower(): platform for platform in platforms}
    accepted_platform_names = sorted(platform.name for platform in platforms)
    accepted_platforms_text = _format_platform_list(platforms)

    inserted_count = 0
    skipped_duplicate_count = 0
    exception_count = 0
    failed_count = 0
    row_results: list[ImportRowResult] = []

    for index, row in enumerate(csv_rows, start=2):
        employee_name = row["employee_name"]
        staff_id = row["staff_id"]
        email = row["email"]
        emp_new_id = row["emp_new_id"]
        platform_name = row["platform_name"]

        if not staff_id:
            exception_count += 1
            _log_row_issue("warning", "Missing required StaffID for bulk import row", index, row)
            row_results.append(
                ImportRowResult(
                    row_number=index,
                    status="exception",
                    employee_name=employee_name,
                    staff_id=staff_id,
                    emp_new_id=emp_new_id,
                    email=email,
                    platform_name=platform_name,
                    message="Missing required StaffID. Bulk import resolves employees by StaffID only.",
                )
            )
            continue

        if not platform_name:
            exception_count += 1
            _log_row_issue("warning", "Missing platform name for bulk import row", index, row)
            row_results.append(
                ImportRowResult(
                    row_number=index,
                    status="exception",
                    employee_name=employee_name,
                    staff_id=staff_id,
                    emp_new_id=emp_new_id,
                    email=email,
                    platform_name=platform_name,
                    message="Missing platform name.",
                )
            )
            continue

        platform = _resolve_platform(platform_by_name, platform_name)
        if not platform:
            exception_count += 1
            _log_row_issue("warning", "Platform not found in master table", index, row)
            row_results.append(
                ImportRowResult(
                    row_number=index,
                    status="exception",
                    employee_name=employee_name,
                    staff_id=staff_id,
                    emp_new_id=emp_new_id,
                    email=email,
                    platform_name=platform_name,
                    message=(
                        "Platform not found in master table. "
                        f"Use one of: {accepted_platforms_text}."
                    ),
                )
            )
            continue

        employee, resolve_error = _resolve_local_employee(db, row)
        if not employee:
            exception_count += 1
            _log_row_issue("warning", resolve_error or "Employee could not be resolved from StaffID", index, row)
            row_results.append(
                ImportRowResult(
                    row_number=index,
                    status="exception",
                    employee_name=employee_name,
                    staff_id=staff_id,
                    emp_new_id=emp_new_id,
                    email=email,
                    platform_name=platform_name,
                    message=resolve_error or "Employee could not be resolved from StaffID.",
                )
            )
            continue

        if find_active_allocation_id(db, employee.id, platform.id):
            skipped_duplicate_count += 1
            row_results.append(
                ImportRowResult(
                    row_number=index,
                    status="skipped_duplicate",
                    employee_name=employee_name,
                    staff_id=staff_id,
                    emp_new_id=emp_new_id,
                    email=email,
                    platform_name=platform_name,
                    message="Active allocation already exists.",
                )
            )
            continue

        if find_pending_request_id(db, employee.id, platform.id, "assign"):
            skipped_duplicate_count += 1
            row_results.append(
                ImportRowResult(
                    row_number=index,
                    status="skipped_duplicate",
                    employee_name=employee_name,
                    staff_id=staff_id,
                    emp_new_id=emp_new_id,
                    email=email,
                    platform_name=platform_name,
                    message="Pending assign request already exists.",
                )
            )
            continue

        if find_pending_queue_item_id(db, employee.id, platform.id, "assign"):
            skipped_duplicate_count += 1
            row_results.append(
                ImportRowResult(
                    row_number=index,
                    status="skipped_duplicate",
                    employee_name=employee_name,
                    staff_id=staff_id,
                    emp_new_id=emp_new_id,
                    email=email,
                    platform_name=platform_name,
                    message="Pending assign queue item already exists.",
                )
            )
            continue

        if employee.project_id is None or employee.account_id is None:
            exception_count += 1
            _log_row_issue("warning", "Employee missing project/account scope", index, row)
            row_results.append(
                ImportRowResult(
                    row_number=index,
                    status="exception",
                    employee_name=employee_name,
                    staff_id=staff_id,
                    emp_new_id=emp_new_id,
                    email=email,
                    platform_name=platform_name,
                    message="Employee is missing project/account scope.",
                )
            )
            continue

        try:
            monthly_cost = calculate_platform_monthly_unit_cost_for_platform(db, platform)
            if dry_run:
                inserted_count += 1
                row_results.append(
                    ImportRowResult(
                        row_number=index,
                        status="would_insert",
                        employee_name=employee_name,
                        staff_id=staff_id,
                        emp_new_id=emp_new_id,
                        email=email,
                        platform_name=platform_name,
                        message="Row validated successfully in dry-run mode.",
                    )
                )
                continue

            queue_item = QueueItem(
                source_type="import",
                employee_id=employee.id,
                platform_id=platform.id,
                action_type="assign",
                project_id=employee.project_id,
                cost_snapshot_monthly=monthly_cost,
                requested_by_user_id=requested_by_user_id,
                status="executed",
                approval_stage="bulk_import",
                assigned_approval_role="system",
                executed_by_user_id=requested_by_user_id,
                executed_at=datetime.utcnow(),
                execution_notes=f"Bulk CSV import row {index}",
            )
            db.add(queue_item)
            db.flush()

            create_assignment_allocation(
                db,
                employee_id=employee.id,
                platform_id=platform.id,
                project_id=employee.project_id,
                account_id=employee.account_id,
                effective_date=effective_date or date.today(),
                monthly_cost=monthly_cost,
                changed_by_user_id=requested_by_user_id,
                notes=f"Bulk CSV import row {index}",
            )

            inserted_count += 1
            row_results.append(
                ImportRowResult(
                    row_number=index,
                    status="inserted",
                    employee_name=employee_name,
                    staff_id=staff_id,
                    emp_new_id=emp_new_id,
                    email=email,
                    platform_name=platform_name,
                    message="License assigned successfully.",
                )
            )
        except Exception as exc:
            db.rollback()
            failed_count += 1
            _log_row_issue("error", "Failed to process bulk import row", index, row, exc)
            row_results.append(
                ImportRowResult(
                    row_number=index,
                    status="failed",
                    employee_name=employee_name,
                    staff_id=staff_id,
                    emp_new_id=emp_new_id,
                    email=email,
                    platform_name=platform_name,
                    message=f"Failed to process row: {exc}",
                )
            )

    if dry_run:
        db.rollback()
    else:
        db.commit()

    error_row_numbers = [
        result.row_number for result in row_results if result.status in {"exception", "failed"}
    ]
    has_errors = bool(error_row_numbers)
    if has_errors:
        summary_message = (
            "CSV contains one or more invalid rows. "
            f"Review row_results and error_row_numbers: {error_row_numbers}."
        )
    else:
        summary_message = "CSV processed successfully with no row-level errors."

    return ImportSummary(
        total_rows=len(csv_rows),
        inserted_count=inserted_count,
        skipped_duplicate_count=skipped_duplicate_count,
        exception_count=exception_count,
        failed_count=failed_count,
        has_errors=has_errors,
        error_row_numbers=error_row_numbers,
        summary_message=summary_message,
        accepted_platform_names=accepted_platform_names,
        row_results=row_results,
    )