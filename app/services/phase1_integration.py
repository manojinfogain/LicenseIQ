"""
Phase 1 SP Integration Service

Provides feature-flagged access to Phase 1 stored procedures with automatic
ORM fallback. All functions use the feature flag to decide between SP and ORM paths.

Usage:
    from app.services.phase1_integration import get_role_mapping_phase1, get_open_alerts_phase1
    
    # These automatically use SP if USE_PHASE1_SPS=true, ORM if false
    role = get_role_mapping_phase1(db, staff_id="EMP123")
    alerts = get_open_alerts_phase1(db)
"""

from typing import Optional, Any
from sqlalchemy.orm import Session
import logging

from app.core.feature_flags import is_phase1_enabled, log_sp_usage
from app.services.phase1_sp_wrappers import (
    exec_usp_GetRoleMapping,
    exec_usp_GetOpenAlerts,
    exec_usp_GetLicenseRequests,
    exec_usp_GetPendingQueueItems,
    exec_usp_GetPlatformById,
)
from app.models.access import EmployeeWiseRoleMapping
from app.models.license import Alert, LicenseRequest, QueueItem
from app.models.platform import Platform
from sqlalchemy import select

logger = logging.getLogger(__name__)


def get_role_mapping_phase1(db: Session, staff_id: Optional[str]) -> Optional[dict]:
    """
    Get role mapping by staff ID using Phase 1 SP if enabled, ORM fallback.
    
    Args:
        db: SQLAlchemy session
        staff_id: Aspire staff ID
        
    Returns:
        Dict with role_code and scope_ref_id, or None if not found
    """
    if not staff_id:
        return None
    
    if is_phase1_enabled():
        try:
            log_sp_usage("get_role_mapping", True)
            result = exec_usp_GetRoleMapping(db, staff_id)
            return result[0] if result else None  # SP returns list; take first row
        except Exception as exc:
            logger.warning(f"Phase 1 SP failed for role mapping: {exc}. Using ORM.", exc_info=True)
    
    # ORM fallback
    log_sp_usage("get_role_mapping", False)
    mapping = db.scalar(
        select(EmployeeWiseRoleMapping)
        .where(
            EmployeeWiseRoleMapping.emp_staffid == staff_id.strip(),
            EmployeeWiseRoleMapping.is_active == True
        )
    )
    if not mapping:
        return None
    
    return {
        "role_code": mapping.role.code if mapping.role else None,
        "scope_ref_id": mapping.scope_ref_id,
    }


def get_open_alerts_phase1(db: Session) -> list[dict]:
    """
    Get open alerts using Phase 1 SP if enabled, ORM fallback.
    
    Returns:
        List of alert dicts
    """
    if is_phase1_enabled():
        try:
            log_sp_usage("get_open_alerts", True)
            result = exec_usp_GetOpenAlerts(db)
            return result or []
        except Exception as exc:
            logger.warning(f"Phase 1 SP failed for alerts: {exc}. Using ORM.", exc_info=True)
    
    # ORM fallback
    log_sp_usage("get_open_alerts", False)
    alerts = list(db.scalars(
        select(Alert)
        .where(Alert.status == "open")
        .order_by(Alert.priority.desc(), Alert.created_at.desc())
    ).all())
    
    # Convert to dicts matching SP output
    return [
        {
            "id": alert.id,
            "employee_id": alert.employee_id,
            "platform_id": alert.platform_id,
            "alert_type": alert.alert_type,
            "status": alert.status,
            "priority": alert.priority,
            "reason": alert.reason,
            "created_at": alert.created_at,
        }
        for alert in alerts
    ]


def get_license_requests_phase1(db: Session, staff_id: Optional[str] = None) -> list[dict]:
    """
    Get license requests using Phase 1 SP if enabled, ORM fallback.
    
    Args:
        db: SQLAlchemy session
        staff_id: Optional staff ID to filter by
        
    Returns:
        List of request dicts
    """
    if is_phase1_enabled():
        try:
            log_sp_usage("get_license_requests", True)
            result = exec_usp_GetLicenseRequests(db, staff_id=staff_id)
            return result or []
        except Exception as exc:
            logger.warning(f"Phase 1 SP failed for license requests: {exc}. Using ORM.", exc_info=True)
    
    # ORM fallback
    log_sp_usage("get_license_requests", False)
    stmt = select(LicenseRequest).order_by(LicenseRequest.created_at.desc())
    
    if staff_id:
        stmt = stmt.where(LicenseRequest.requested_by_staffid == staff_id.strip())
    
    requests = list(db.scalars(stmt).all())
    
    # Convert to dicts matching SP output
    return [
        {
            "id": req.id,
            "employee_id": req.employee_id,
            "platform_id": req.platform_id,
            "request_type": req.request_type,
            "approval_status": req.approval_status,
            "created_at": req.created_at,
            "requested_by_staffid": req.requested_by_staffid,
        }
        for req in requests
    ]


def get_pending_queue_items_phase1(db: Session) -> list[dict]:
    """
    Get pending queue items using Phase 1 SP if enabled, ORM fallback.
    
    Returns:
        List of queue item dicts
    """
    if is_phase1_enabled():
        try:
            log_sp_usage("get_pending_queue_items", True)
            result = exec_usp_GetPendingQueueItems(db)
            return result or []
        except Exception as exc:
            logger.warning(f"Phase 1 SP failed for queue items: {exc}. Using ORM.", exc_info=True)
    
    # ORM fallback
    log_sp_usage("get_pending_queue_items", False)
    items = list(db.scalars(
        select(QueueItem)
        .where(QueueItem.status == "pending")
        .order_by(QueueItem.created_at.desc())
    ).all())
    
    # Convert to dicts matching SP output
    return [
        {
            "id": item.id,
            "employee_id": item.employee_id,
            "platform_id": item.platform_id,
            "action_type": item.action_type,
            "status": item.status,
            "created_at": item.created_at,
        }
        for item in items
    ]


def get_platform_by_id_phase1(db: Session, platform_id: int) -> Optional[dict]:
    """
    Get platform by ID using Phase 1 SP if enabled, ORM fallback.
    
    Args:
        db: SQLAlchemy session
        platform_id: Platform ID
        
    Returns:
        Platform dict or None if not found
    """
    if is_phase1_enabled():
        try:
            log_sp_usage("get_platform_by_id", True)
            result = exec_usp_GetPlatformById(db, platform_id)
            return result  # Returns dict or None
        except Exception as exc:
            logger.warning(f"Phase 1 SP failed for platform lookup: {exc}. Using ORM.", exc_info=True)
    
    # ORM fallback
    log_sp_usage("get_platform_by_id", False)
    platform = db.get(Platform, platform_id)
    if not platform:
        return None
    
    return {
        "id": platform.id,
        "name": platform.name,
        "vendor": platform.vendor,
        "category": platform.category,
        "is_active": platform.is_active,
    }
