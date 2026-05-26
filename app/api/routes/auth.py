import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.error_utils import handle_database_error, handle_unexpected_error
from app.core.aspire_database import AspireSessionLocal
from app.core.audit_logger import audit_log
from app.core.config import settings
from app.core.limiter import limiter
from app.services.login_accounts import verify_login_credentials
from app.models.aspire import AspireEmployee
from app.schemas.auth import LoginRequest, LoginResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def _initials(full_name: str) -> str:
    parts = full_name.strip().split()
    return "".join(p[0].upper() for p in parts if p)[:3]


def _pick_preferred_employee(candidates: list[AspireEmployee]) -> AspireEmployee | None:
    """When multiple ERM rows share an email, prefer an active employee."""
    if not candidates:
        return None
    active = [e for e in candidates if e.is_active]
    if active:
        return active[0]
    return candidates[0]


def _lookup_aspire_employee_by_email(aspire_db: Session, email: str) -> AspireEmployee | None:
    normalized = email.strip().lower()
    exact_matches = list(
        aspire_db.scalars(
            select(AspireEmployee).where(
                func.lower(func.rtrim(AspireEmployee.emp_mailid)) == normalized
            )
        ).all()
    )
    employee = _pick_preferred_employee(exact_matches)
    if employee:
        return employee

    if "@" in normalized:
        local_part = normalized.split("@")[0]
        local_matches = list(
            aspire_db.scalars(
                select(AspireEmployee).where(
                    func.lower(func.rtrim(AspireEmployee.emp_mailid)).like(local_part + "@%")
                )
            ).all()
        )
        return _pick_preferred_employee(local_matches)
    return None


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    email = payload.email.strip().lower()
    source_ip = request.client.host if request.client else "unknown"
    invalid_detail = "Invalid email or password."

    allowlisted = verify_login_credentials(db, email, payload.password)
    if not allowlisted:
        audit_log.log_auth_failure(
            email=email,
            reason="Not on login allowlist or wrong password",
            source_ip=source_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=invalid_detail,
        )

    try:
        aspire_db = AspireSessionLocal()
        try:
            employee = _lookup_aspire_employee_by_email(aspire_db, email)
            if not employee:
                audit_log.log_auth_failure(
                    email=email,
                    reason="Allowlisted user not found in Aspire employee master",
                    source_ip=source_ip,
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=invalid_detail,
                )

            staffid = (employee.emp_staffid or "").strip()
            display_name = employee.full_name or staffid
            audit_log.log_auth_success(
                email=employee.email or email,
                staffid=staffid,
                user_id=None,
                role=allowlisted.role_code,
            )
            logger.info("Login success role=%s (allowlist)", allowlisted.role_code)

            is_dev = settings.app_env.lower() == "dev"
            return LoginResponse(
                role=allowlisted.role_code,
                name=display_name,
                ini=_initials(display_name),
                dept=allowlisted.role_name,
                email=(employee.email or email) if is_dev else "",
                staffid=staffid,
                role_source="database",
            )
        finally:
            aspire_db.close()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "login")
    except Exception as exc:
        handle_unexpected_error(db, exc, "login")
