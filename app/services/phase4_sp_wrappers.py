"""Phase 4 Stored Procedure Wrappers: Queue Execution & Alert Operations"""

from datetime import date, datetime
from sqlalchemy import text
from sqlalchemy.orm import Session


class Phase4SPError(Exception):
    """Raised when a Phase 4 stored procedure call fails."""


def execute_queue_item_assignment(
    db: Session,
    queue_item_id: int,
    executed_by_user_id: int,
    execution_notes: str | None = None,
) -> None:
    """
    Execute usp_ExecuteQueueItemAssignment stored procedure.
    Creates license allocation from queue item assignment.
    """
    try:
        db.execute(
            text(
                """
                EXEC dbo.usp_ExecuteQueueItemAssignment
                    @QueueItemId = :queue_item_id,
                    @ExecutedByUserId = :executed_by_user_id,
                    @ExecutionNotes = :execution_notes;
                """
            ),
            {
                "queue_item_id": queue_item_id,
                "executed_by_user_id": executed_by_user_id,
                "execution_notes": execution_notes,
            },
        )
    except Exception as exc:
        raise Phase4SPError(f"usp_ExecuteQueueItemAssignment failed: {exc}") from exc


def execute_queue_item_revocation(
    db: Session,
    queue_item_id: int,
    executed_by_user_id: int,
    execution_notes: str | None = None,
) -> None:
    """
    Execute usp_ExecuteQueueItemRevocation stored procedure.
    Revokes license allocation from queue item revocation.
    """
    try:
        db.execute(
            text(
                """
                EXEC dbo.usp_ExecuteQueueItemRevocation
                    @QueueItemId = :queue_item_id,
                    @ExecutedByUserId = :executed_by_user_id,
                    @ExecutionNotes = :execution_notes;
                """
            ),
            {
                "queue_item_id": queue_item_id,
                "executed_by_user_id": executed_by_user_id,
                "execution_notes": execution_notes,
            },
        )
    except Exception as exc:
        raise Phase4SPError(f"usp_ExecuteQueueItemRevocation failed: {exc}") from exc


def mark_queue_item_executed(
    db: Session,
    queue_item_id: int,
    executed_by_user_id: int | None = None,
    execution_notes: str | None = None,
) -> None:
    """
    Execute usp_MarkQueueItemExecuted stored procedure.
    Marks a queue item as executed.
    """
    try:
        db.execute(
            text(
                """
                EXEC dbo.usp_MarkQueueItemExecuted
                    @QueueItemId = :queue_item_id,
                    @ExecutedByUserId = :executed_by_user_id,
                    @ExecutionNotes = :execution_notes;
                """
            ),
            {
                "queue_item_id": queue_item_id,
                "executed_by_user_id": executed_by_user_id,
                "execution_notes": execution_notes,
            },
        )
    except Exception as exc:
        raise Phase4SPError(f"usp_MarkQueueItemExecuted failed: {exc}") from exc


def create_alert(
    db: Session,
    alert_type: str,
    priority: str,
    reason: str,
    employee_id: int | None = None,
    platform_id: int | None = None,
    detail: str | None = None,
    source_system: str = "manual",
) -> int:
    """
    Execute usp_CreateAlert stored procedure.
    Creates a new alert and returns the alert ID.
    """
    try:
        result = db.execute(
            text(
                """
                DECLARE @CreatedAlertId INT;
                
                EXEC dbo.usp_CreateAlert
                    @EmployeeId = :employee_id,
                    @PlatformId = :platform_id,
                    @AlertType = :alert_type,
                    @Priority = :priority,
                    @Reason = :reason,
                    @Detail = :detail,
                    @SourceSystem = :source_system,
                    @CreatedAlertId = @CreatedAlertId OUTPUT;
                
                SELECT @CreatedAlertId AS alert_id;
                """
            ),
            {
                "employee_id": employee_id,
                "platform_id": platform_id,
                "alert_type": alert_type,
                "priority": priority,
                "reason": reason,
                "detail": detail,
                "source_system": source_system,
            },
        ).fetchone()
        return int(result[0]) if result else None
    except Exception as exc:
        raise Phase4SPError(f"usp_CreateAlert failed: {exc}") from exc


def resolve_alert(
    db: Session,
    alert_id: int,
) -> None:
    """
    Execute usp_ResolveAlert stored procedure.
    Marks an alert as resolved.
    """
    try:
        db.execute(
            text(
                """
                EXEC dbo.usp_ResolveAlert
                    @AlertId = :alert_id;
                """
            ),
            {
                "alert_id": alert_id,
            },
        )
    except Exception as exc:
        raise Phase4SPError(f"usp_ResolveAlert failed: {exc}") from exc


def get_queue_metrics(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """
    Execute usp_GetQueueMetrics stored procedure.
    Returns queue and alert performance metrics.
    """
    try:
        result = db.execute(
            text(
                """
                EXEC dbo.usp_GetQueueMetrics
                    @StartDate = :start_date,
                    @EndDate = :end_date;
                """
            ),
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        ).fetchone()
        
        if result:
            return {
                "pending_count": result[0],
                "executed_count": result[1],
                "rejected_count": result[2],
                "open_alerts": result[3],
                "resolved_alerts": result[4],
                "avg_queue_time_minutes": result[5],
            }
        return {}
    except Exception as exc:
        raise Phase4SPError(f"usp_GetQueueMetrics failed: {exc}") from exc
