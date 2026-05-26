"""
Phase 4 integration service for queue execution and alert operations.

Uses stored procedures when Phase 4 is enabled and falls back to the existing
ORM implementation only when the feature flag is disabled.
"""

import logging
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.feature_flags import is_phase4_queue_alerts_enabled, log_sp_usage, Phase4SPError
from app.models.license import QueueItem, LicenseAllocation, AllocationAudit, Alert
from app.services.phase4_sp_wrappers import (
    execute_queue_item_assignment as sp_execute_queue_item_assignment,
    execute_queue_item_revocation as sp_execute_queue_item_revocation,
    mark_queue_item_executed as sp_mark_queue_item_executed,
    create_alert as sp_create_alert,
    resolve_alert as sp_resolve_alert,
    get_queue_metrics as sp_get_queue_metrics,
)

logger = logging.getLogger(__name__)


def _execute_queue_item_assignment_orm(
    db: Session,
    queue_item_id: int,
    executed_by_user_id: int,
    execution_notes: str | None = None,
) -> None:
    """Execute queue item assignment using ORM."""
    queue_item = db.get(QueueItem, queue_item_id)
    if not queue_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue item not found")
    
    # Check for existing active allocation
    existing = db.query(LicenseAllocation).filter_by(
        employee_id=queue_item.employee_id,
        platform_id=queue_item.platform_id,
        status="active",
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Active allocation already exists")
    
    # Create allocation
    allocation = LicenseAllocation(
        employee_id=queue_item.employee_id,
        platform_id=queue_item.platform_id,
        project_id=queue_item.project_id,
        account_id=None,
        status="active",
        effective_date=date.today(),
        monthly_cost=queue_item.cost_snapshot_monthly,
        source_type="queue_executed",
    )
    db.add(allocation)
    
    # Mark queue item as executed
    queue_item.status = "executed"
    queue_item.executed_by_user_id = executed_by_user_id
    queue_item.execution_notes = execution_notes
    db.add(queue_item)
    
    db.commit()


def _execute_queue_item_revocation_orm(
    db: Session,
    queue_item_id: int,
    executed_by_user_id: int,
    execution_notes: str | None = None,
) -> None:
    """Execute queue item revocation using ORM."""
    queue_item = db.get(QueueItem, queue_item_id)
    if not queue_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue item not found")
    
    # Find active allocation — use most recently created to handle multiple active rows correctly
    allocation = (
        db.query(LicenseAllocation)
        .filter_by(
            employee_id=queue_item.employee_id,
            platform_id=queue_item.platform_id,
            status="active",
        )
        .order_by(LicenseAllocation.id.desc())
        .first()
    )
    if not allocation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active allocation found")
    
    # Mark allocation as revoked
    allocation.status = "revoked"
    allocation.revoked_date = date.today()
    db.add(allocation)
    
    # Record audit
    audit = AllocationAudit(
        allocation_id=allocation.id,
        event_type="revocation",
        event_source="queue_executed",
        old_status="active",
        new_status="revoked",
        changed_by_user_id=executed_by_user_id,
        notes=execution_notes,
    )
    db.add(audit)
    
    # Mark queue item as executed
    queue_item.status = "executed"
    queue_item.executed_by_user_id = executed_by_user_id
    queue_item.execution_notes = execution_notes
    db.add(queue_item)
    
    db.commit()


def _mark_queue_item_executed_orm(
    db: Session,
    queue_item_id: int,
    executed_by_user_id: int | None = None,
    execution_notes: str | None = None,
) -> None:
    """Mark queue item as executed using ORM."""
    queue_item = db.get(QueueItem, queue_item_id)
    if not queue_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue item not found")
    
    queue_item.status = "executed"
    queue_item.executed_by_user_id = executed_by_user_id
    queue_item.execution_notes = execution_notes
    db.add(queue_item)
    db.commit()


def _create_alert_orm(
    db: Session,
    alert_type: str,
    priority: str,
    reason: str,
    employee_id: int | None = None,
    platform_id: int | None = None,
    detail: str | None = None,
    source_system: str = "manual",
) -> int:
    """Create alert using ORM."""
    alert = Alert(
        employee_id=employee_id,
        platform_id=platform_id,
        alert_type=alert_type,
        priority=priority,
        reason=reason,
        detail=detail,
        source_system=source_system,
        status="open",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert.id


def _resolve_alert_orm(
    db: Session,
    alert_id: int,
) -> None:
    """Resolve alert using ORM."""
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    
    alert.status = "resolved"
    db.add(alert)
    db.commit()


def _get_queue_metrics_orm(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Get queue metrics using ORM."""
    from datetime import timedelta
    
    if start_date is None:
        start_date = date.today() - timedelta(days=30)
    if end_date is None:
        end_date = date.today()
    
    pending = db.query(QueueItem).filter(
        QueueItem.status == "pending",
        QueueItem.created_at >= start_date,
    ).count()
    
    executed = db.query(QueueItem).filter(
        QueueItem.status == "executed",
        QueueItem.executed_at >= start_date,
    ).count()
    
    rejected = db.query(QueueItem).filter(
        QueueItem.status == "rejected",
        QueueItem.created_at >= start_date,
    ).count()
    
    open_alerts = db.query(Alert).filter(
        Alert.status == "open",
        Alert.created_at >= start_date,
    ).count()
    
    resolved_alerts = db.query(Alert).filter(
        Alert.status == "resolved",
        Alert.resolved_at >= start_date,
    ).count()
    
    return {
        "pending_count": pending,
        "executed_count": executed,
        "rejected_count": rejected,
        "open_alerts": open_alerts,
        "resolved_alerts": resolved_alerts,
        "avg_queue_time_minutes": None,  # ORM doesn't easily calculate this
    }


# Integration functions with feature flag support
def execute_queue_item_assignment_phase4(
    db: Session,
    queue_item_id: int,
    executed_by_user_id: int,
    execution_notes: str | None = None,
) -> None:
    """Execute queue item assignment using Phase 4 SP when enabled, ORM otherwise."""
    if is_phase4_queue_alerts_enabled():
        try:
            log_sp_usage("execute_queue_item_assignment", True)
            sp_execute_queue_item_assignment(
                db,
                queue_item_id=queue_item_id,
                executed_by_user_id=executed_by_user_id,
                execution_notes=execution_notes,
            )
            db.expire_all()
        except HTTPException:
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Phase 4 SP failed for execute queue item assignment")
            raise Phase4SPError("Phase 4 execute queue item assignment failed") from exc
    else:
        log_sp_usage("execute_queue_item_assignment", False)
        _execute_queue_item_assignment_orm(
            db,
            queue_item_id=queue_item_id,
            executed_by_user_id=executed_by_user_id,
            execution_notes=execution_notes,
        )


def execute_queue_item_revocation_phase4(
    db: Session,
    queue_item_id: int,
    executed_by_user_id: int,
    execution_notes: str | None = None,
) -> None:
    """Execute queue item revocation using Phase 4 SP when enabled, ORM otherwise."""
    if is_phase4_queue_alerts_enabled():
        try:
            log_sp_usage("execute_queue_item_revocation", True)
            sp_execute_queue_item_revocation(
                db,
                queue_item_id=queue_item_id,
                executed_by_user_id=executed_by_user_id,
                execution_notes=execution_notes,
            )
            db.expire_all()
        except HTTPException:
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Phase 4 SP failed for execute queue item revocation")
            raise Phase4SPError("Phase 4 execute queue item revocation failed") from exc
    else:
        log_sp_usage("execute_queue_item_revocation", False)
        _execute_queue_item_revocation_orm(
            db,
            queue_item_id=queue_item_id,
            executed_by_user_id=executed_by_user_id,
            execution_notes=execution_notes,
        )


def mark_queue_item_executed_phase4(
    db: Session,
    queue_item_id: int,
    executed_by_user_id: int | None = None,
    execution_notes: str | None = None,
) -> None:
    """Mark queue item executed using Phase 4 SP when enabled, ORM otherwise."""
    if is_phase4_queue_alerts_enabled():
        try:
            log_sp_usage("mark_queue_item_executed", True)
            sp_mark_queue_item_executed(
                db,
                queue_item_id=queue_item_id,
                executed_by_user_id=executed_by_user_id,
                execution_notes=execution_notes,
            )
            db.expire_all()
        except HTTPException:
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Phase 4 SP failed for mark queue item executed")
            raise Phase4SPError("Phase 4 mark queue item executed failed") from exc
    else:
        log_sp_usage("mark_queue_item_executed", False)
        _mark_queue_item_executed_orm(
            db,
            queue_item_id=queue_item_id,
            executed_by_user_id=executed_by_user_id,
            execution_notes=execution_notes,
        )


def create_alert_phase4(
    db: Session,
    alert_type: str,
    priority: str,
    reason: str,
    employee_id: int | None = None,
    platform_id: int | None = None,
    detail: str | None = None,
    source_system: str = "manual",
) -> int:
    """Create alert using Phase 4 SP when enabled, ORM otherwise."""
    if is_phase4_queue_alerts_enabled():
        try:
            log_sp_usage("create_alert", True)
            alert_id = sp_create_alert(
                db,
                alert_type=alert_type,
                priority=priority,
                reason=reason,
                employee_id=employee_id,
                platform_id=platform_id,
                detail=detail,
                source_system=source_system,
            )
            return alert_id
        except HTTPException:
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Phase 4 SP failed for create alert")
            raise Phase4SPError("Phase 4 create alert failed") from exc
    else:
        log_sp_usage("create_alert", False)
        return _create_alert_orm(
            db,
            alert_type=alert_type,
            priority=priority,
            reason=reason,
            employee_id=employee_id,
            platform_id=platform_id,
            detail=detail,
            source_system=source_system,
        )


def resolve_alert_phase4(
    db: Session,
    alert_id: int,
) -> None:
    """Resolve alert using Phase 4 SP when enabled, ORM otherwise."""
    if is_phase4_queue_alerts_enabled():
        try:
            log_sp_usage("resolve_alert", True)
            sp_resolve_alert(db, alert_id=alert_id)
            db.expire_all()
        except HTTPException:
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Phase 4 SP failed for resolve alert")
            raise Phase4SPError("Phase 4 resolve alert failed") from exc
    else:
        log_sp_usage("resolve_alert", False)
        _resolve_alert_orm(db, alert_id=alert_id)


def get_queue_metrics_phase4(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Get queue metrics using Phase 4 SP when enabled, ORM otherwise."""
    if is_phase4_queue_alerts_enabled():
        try:
            log_sp_usage("get_queue_metrics", True)
            return sp_get_queue_metrics(db, start_date=start_date, end_date=end_date)
        except Exception as exc:
            logger.exception("Phase 4 SP failed for get queue metrics")
            raise Phase4SPError("Phase 4 get queue metrics failed") from exc
    else:
        log_sp_usage("get_queue_metrics", False)
        return _get_queue_metrics_orm(db, start_date=start_date, end_date=end_date)
