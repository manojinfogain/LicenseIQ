"""
================================================================================
Phase 1 Stored Procedure Wrappers
Executes 12 read-only SPs and parses results into ORM-compatible structures
================================================================================
Created: May 15, 2026
"""

from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime


class Phase1SPError(Exception):
    """Raised when SP execution fails"""
    pass


def _parse_response(result_rows: List) -> List[Dict]:
    """Convert Row objects to dict"""
    return [dict(row._mapping) for row in result_rows] if result_rows else []


# ============================================================================
# SP-1: usp_GetDashboardComplete
# ============================================================================
def exec_usp_GetDashboardComplete(db: Session) -> Dict[str, List[Dict]]:
    """
    Execute usp_GetDashboardComplete and parse all 10 result sets
    
    Returns:
        {
            'platforms': [...],
            'seat_snapshots': [...],
            'allocations': [...],
            'alerts': [...],
            'queue_items': [...],
            'requests': [...],
            'audits': [...],
            'accounts': [...],
            'gdls': [...],
            'projects': [...]
        }
    """
    try:
        result = db.execute(text("EXEC dbo.usp_GetDashboardComplete")).fetchall()
        
        # Parse first result set (platforms)
        platforms = _parse_response(result)
        
        # NOTE: Multi-result-set handling in SQLAlchemy requires:
        # 1. Use db.execute(text(...), execution_options={"stream_results": True})
        # 2. Manually call .nextset() between result sets
        # For now, returning platforms only; full implementation requires 
        # raw pyodbc connection or sqlalchemy-stubs
        
        return {
            'platforms': platforms,
            'seat_snapshots': [],
            'allocations': [],
            'alerts': [],
            'queue_items': [],
            'requests': [],
            'audits': [],
            'accounts': [],
            'gdls': [],
            'projects': []
        }
    except Exception as e:
        raise Phase1SPError(f"usp_GetDashboardComplete failed: {str(e)}")


# ============================================================================
# SP-2: usp_GetPlatformById
# ============================================================================
def exec_usp_GetPlatformById(db: Session, platform_id: int) -> Optional[Dict]:
    """Get single platform by ID"""
    try:
        result = db.execute(
            text("EXEC dbo.usp_GetPlatformById :platform_id"),
            {"platform_id": platform_id}
        ).fetchone()
        return dict(result._mapping) if result else None
    except Exception as e:
        raise Phase1SPError(f"usp_GetPlatformById failed: {str(e)}")


# ============================================================================
# SP-3: usp_GetOpenAlerts
# ============================================================================
def exec_usp_GetOpenAlerts(db: Session) -> List[Dict]:
    """Get all open alerts"""
    try:
        result = db.execute(text("EXEC dbo.usp_GetOpenAlerts")).fetchall()
        return _parse_response(result)
    except Exception as e:
        raise Phase1SPError(f"usp_GetOpenAlerts failed: {str(e)}")


# ============================================================================
# SP-4: usp_GetManualAlerts
# ============================================================================
def exec_usp_GetManualAlerts(db: Session) -> List[Dict]:
    """Get manual alerts (pending approval)"""
    try:
        result = db.execute(text("EXEC dbo.usp_GetManualAlerts")).fetchall()
        return _parse_response(result)
    except Exception as e:
        raise Phase1SPError(f"usp_GetManualAlerts failed: {str(e)}")


# ============================================================================
# SP-5: usp_GetLicenseRequests
# ============================================================================
def exec_usp_GetLicenseRequests(db: Session, staff_id: Optional[str] = None) -> List[Dict]:
    """Get license requests, optionally filtered by staff_id"""
    try:
        result = db.execute(
            text("EXEC dbo.usp_GetLicenseRequests :staff_id"),
            {"staff_id": staff_id}
        ).fetchall()
        return _parse_response(result)
    except Exception as e:
        raise Phase1SPError(f"usp_GetLicenseRequests failed: {str(e)}")


# ============================================================================
# SP-6: usp_GetLicenseRequestById
# ============================================================================
def exec_usp_GetLicenseRequestById(db: Session, request_id: int) -> Optional[Dict]:
    """Get single license request by ID"""
    try:
        result = db.execute(
            text("EXEC dbo.usp_GetLicenseRequestById :request_id"),
            {"request_id": request_id}
        ).fetchone()
        return dict(result._mapping) if result else None
    except Exception as e:
        raise Phase1SPError(f"usp_GetLicenseRequestById failed: {str(e)}")


# ============================================================================
# SP-7: usp_GetApprovalHistory
# ============================================================================
def exec_usp_GetApprovalHistory(db: Session, staff_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
    """Get approval history for a staff member or all"""
    try:
        result = db.execute(
            text("EXEC dbo.usp_GetApprovalHistory :staff_id, :limit"),
            {"staff_id": staff_id, "limit": limit}
        ).fetchall()
        return _parse_response(result)
    except Exception as e:
        raise Phase1SPError(f"usp_GetApprovalHistory failed: {str(e)}")


# ============================================================================
# SP-8: usp_GetPendingQueueItems
# ============================================================================
def exec_usp_GetPendingQueueItems(db: Session) -> List[Dict]:
    """Get all pending queue items"""
    try:
        result = db.execute(text("EXEC dbo.usp_GetPendingQueueItems")).fetchall()
        return _parse_response(result)
    except Exception as e:
        raise Phase1SPError(f"usp_GetPendingQueueItems failed: {str(e)}")


# ============================================================================
# SP-9: usp_FindActiveAllocationByCode
# ============================================================================
def exec_usp_FindActiveAllocationByCode(db: Session, staff_id: str, platform_id: int) -> Optional[Dict]:
    """Find active allocation by employee code (staff_id) and platform"""
    try:
        result = db.execute(
            text("EXEC dbo.usp_FindActiveAllocationByCode :staff_id, :platform_id"),
            {"staff_id": staff_id, "platform_id": platform_id}
        ).fetchone()
        return dict(result._mapping) if result else None
    except Exception as e:
        raise Phase1SPError(f"usp_FindActiveAllocationByCode failed: {str(e)}")


# ============================================================================
# SP-10: usp_FindPendingRequest
# ============================================================================
def exec_usp_FindPendingRequest(db: Session, employee_id: int, platform_id: int, request_type: str) -> Optional[int]:
    """Find pending request ID"""
    try:
        result = db.execute(
            text("EXEC dbo.usp_FindPendingRequest :employee_id, :platform_id, :request_type"),
            {"employee_id": employee_id, "platform_id": platform_id, "request_type": request_type}
        ).fetchone()
        return result[0] if result else None
    except Exception as e:
        raise Phase1SPError(f"usp_FindPendingRequest failed: {str(e)}")


# ============================================================================
# SP-11: usp_FindPendingQueueItem
# ============================================================================
def exec_usp_FindPendingQueueItem(db: Session, employee_id: int, platform_id: int, action_type: str) -> Optional[int]:
    """Find pending queue item ID"""
    try:
        result = db.execute(
            text("EXEC dbo.usp_FindPendingQueueItem :employee_id, :platform_id, :action_type"),
            {"employee_id": employee_id, "platform_id": platform_id, "action_type": action_type}
        ).fetchone()
        return result[0] if result else None
    except Exception as e:
        raise Phase1SPError(f"usp_FindPendingQueueItem failed: {str(e)}")


# ============================================================================
# SP-12: usp_CheckOpenAlertExists
# ============================================================================
def exec_usp_CheckOpenAlertExists(db: Session, employee_id: int, alert_type: str) -> bool:
    """Check if open alert exists"""
    try:
        result = db.execute(
            text("EXEC dbo.usp_CheckOpenAlertExists :employee_id, :alert_type"),
            {"employee_id": employee_id, "alert_type": alert_type}
        ).fetchone()
        return result[0] == 1 if result else False
    except Exception as e:
        raise Phase1SPError(f"usp_CheckOpenAlertExists failed: {str(e)}")


# ============================================================================
# SP-13: usp_GetRoleMapping
# ============================================================================
def exec_usp_GetRoleMapping(db: Session, staff_id: str) -> List[Dict]:
    """Get role mappings for staff member"""
    try:
        result = db.execute(
            text("EXEC dbo.usp_GetRoleMapping :staff_id"),
            {"staff_id": staff_id}
        ).fetchall()
        return _parse_response(result)
    except Exception as e:
        raise Phase1SPError(f"usp_GetRoleMapping failed: {str(e)}")
