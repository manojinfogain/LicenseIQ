from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.error_utils import handle_database_error, handle_unexpected_error
from app.schemas.dashboard import DashboardBootstrapResponse, DashboardSummaryResponse
from app.services.dashboard import build_dashboard_bootstrap, build_dashboard_summary
from app.models.access import EmployeeWiseRoleMapping
from sqlalchemy import select


router = APIRouter()


@router.get("", response_model=DashboardBootstrapResponse)
@router.get("/", response_model=DashboardBootstrapResponse)
def get_dashboard(
    user_id: int | None = Query(default=None),
    staffid: str | None = Query(default=None, description="Aspire EMP_STAFFID (preferred over user_id)"),
    org_level: bool = Query(default=False, description="Return real org-level Aspire data regardless of user scope"),
    db: Session = Depends(get_db),
) -> DashboardBootstrapResponse:
    """Get dashboard bootstrap data (default endpoint for frontend refresh).
    
    This is an alias for /bootstrap to support frontend refresh button.
    Returns queue, employees, platforms, and alerts data.
    
    Supports two modes:
    1. staffid: Direct Aspire staff ID (recommended, uses EmployeeWiseRoleMapping)
    2. user_id: Legacy LicenseIQ user ID (uses User + aspire_staff_id link)
    
    If both provided, staffid takes precedence.
    """
    try:
        if org_level:
            return build_dashboard_bootstrap(db, org_level=True)

        # If staffid provided, use it directly
        if staffid:
            return build_dashboard_bootstrap(db, staffid=staffid)
        
        # Fallback to user_id (legacy)
        return build_dashboard_bootstrap(db, user_id=user_id)
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "get dashboard")
    except Exception as exc:
        handle_unexpected_error(db, exc, "get dashboard")


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    user_id: int | None = Query(default=None),
    staffid: str | None = Query(default=None, description="Aspire EMP_STAFFID (preferred over user_id)"),
    account_id: int | None = Query(default=None),
    project_id: int | None = Query(default=None),
    gdl_id: int | None = Query(default=None),
    unit: str | None = Query(default=None),
    account_name: str | None = Query(default=None),
    project_name: str | None = Query(default=None),
    gdl_code: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> DashboardSummaryResponse:
    """Get dashboard summary/stats scoped to user role.
    
    Supports two modes:
    1. staffid: Direct Aspire staff ID (recommended, uses EmployeeWiseRoleMapping)
    2. user_id: Legacy LicenseIQ user ID (uses User + aspire_staff_id link)
    
    If both provided, staffid takes precedence.
    """
    try:
        return build_dashboard_summary(
            db=db,
            user_id=user_id,
            staffid=staffid,
            account_id=account_id,
            project_id=project_id,
            gdl_id=gdl_id,
            unit=unit,
            account_name=account_name,
            project_name=project_name,
            gdl_code=gdl_code,
        )
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "get dashboard summary")
    except Exception as exc:
        handle_unexpected_error(db, exc, "get dashboard summary")


@router.get("/bootstrap", response_model=DashboardBootstrapResponse)
def get_dashboard_bootstrap(
    user_id: int | None = Query(default=None),
    staffid: str | None = Query(default=None, description="Aspire EMP_STAFFID (preferred over user_id)"),
    org_level: bool = Query(default=False, description="Return real org-level Aspire data regardless of user scope"),
    db: Session = Depends(get_db),
) -> DashboardBootstrapResponse:
    """Get dashboard bootstrap data.
    
    Supports two modes:
    1. staffid: Direct Aspire staff ID (recommended, uses EmployeeWiseRoleMapping)
    2. user_id: Legacy LicenseIQ user ID (uses User + aspire_staff_id link)
    
    If both provided, staffid takes precedence.
    """
    try:
        if org_level:
            return build_dashboard_bootstrap(db, org_level=True)

        # If staffid provided, use it directly (PlanningMonitoring style)
        if staffid:
            return build_dashboard_bootstrap(db, staffid=staffid)
        
        # Fallback to user_id (legacy)
        return build_dashboard_bootstrap(db, user_id=user_id)
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "get dashboard bootstrap")
    except Exception as exc:
        handle_unexpected_error(db, exc, "get dashboard bootstrap")
