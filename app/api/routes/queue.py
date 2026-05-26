from datetime import date, datetime
import logging
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.error_utils import handle_database_error, handle_unexpected_error
from app.api.query_helpers import (
    find_active_allocation_id,
    find_pending_queue_item_id,
    find_pending_request_id,
    resolve_employee_ids,
    resolve_open_alerts_if_no_active_allocations,
    validate_user_exists,
)
from app.models.license import Alert, AllocationAudit, LicenseAllocation, LicenseRequest, QueueItem
from app.models.organization import Employee, Project
from app.models.platform import Platform
from app.schemas.common import MessageResponse
from app.schemas.queue import QueueExecuteRequest, QueueItemRead
from app.services.employee_resolution import resolve_canonical_employee_id
from app.services.license_execution import (
    create_assignment_allocation,
    resolve_assignment_scope,
    revoke_active_allocation,
)
from app.services.pricing import calculate_platform_monthly_unit_cost_for_platform
from app.services import email as email_service
from app.services.phase1_integration import get_pending_queue_items_phase1


class ManualQueueItemCreate(BaseModel):
    employee_id: int
    employee_name: str
    platform_name: str
    action_type: str
    project_id: int
    project_name: str
    created_by: str
    effective_date: str
    source_type: str = "manual"
    execution_notes: str = ""


router = APIRouter()
logger = logging.getLogger(__name__)


def _ensure_assign_not_duplicated(db: Session, employee_id: int, platform_id: int) -> None:
    emp_ids = resolve_employee_ids(db, employee_id)
    active_allocation = find_active_allocation_id(db, emp_ids, platform_id)
    if active_allocation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This employee already has this license assigned.",
        )

    pending_request = find_pending_request_id(db, emp_ids, platform_id, "assign")
    if pending_request:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An assign request for this employee and license is already pending.",
        )

    pending_queue_item = find_pending_queue_item_id(db, emp_ids, platform_id, "assign")
    if pending_queue_item:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This license is already pending assignment for the selected employee.",
        )


def _ensure_revoke_is_valid(db: Session, employee_id: int, platform_id: int) -> None:
    emp_ids = resolve_employee_ids(db, employee_id)
    active_allocation = find_active_allocation_id(db, emp_ids, platform_id)
    if not active_allocation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This employee does not currently have an active allocation for this license.",
        )


@router.get("", response_model=list[QueueItemRead])
def list_queue_items(db: Session = Depends(get_db)) -> list[QueueItemRead]:
    try:
        # Get queue items using Phase 1 SP if enabled, ORM fallback
        item_dicts = get_pending_queue_items_phase1(db)
        
        # Convert dicts back to ORM objects for response serialization
        items = []
        for item_dict in item_dicts:
            item = db.get(QueueItem, item_dict["id"])
            if item:
                items.append(item)
        
        return items
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "list queue items")
    except Exception as exc:
        handle_unexpected_error(db, exc, "list queue items")


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def create_manual_queue_item(
    payload: ManualQueueItemCreate,
    db: Session = Depends(get_db),
) -> MessageResponse:
    try:
        platform = db.scalars(select(Platform).where(Platform.name == payload.platform_name)).first()
        if not platform:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")

        if payload.action_type.lower() == "assign":
            _ensure_assign_not_duplicated(db, payload.employee_id, platform.id)

        if payload.action_type.lower() == "revoke":
            _ensure_revoke_is_valid(db, payload.employee_id, platform.id)
            existing_revoke = find_pending_queue_item_id(db, payload.employee_id, platform.id, "revoke")
            if existing_revoke:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A revoke for {payload.employee_name} — {payload.platform_name} is already in the queue.",
                )

        cost_snapshot = calculate_platform_monthly_unit_cost_for_platform(db, platform)

        queue_item = QueueItem(
            source_type=payload.source_type,
            employee_id=payload.employee_id,
            platform_id=platform.id,
            action_type=payload.action_type,
            project_id=payload.project_id,
            cost_snapshot_monthly=cost_snapshot,
            status="pending",
            execution_notes=payload.execution_notes,
        )
        db.add(queue_item)
        db.commit()

        return MessageResponse(
            message=f"Manual queue item created for {payload.employee_name} — {payload.platform_name}"
        )
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "create manual queue item")
    except Exception as exc:
        handle_unexpected_error(db, exc, "create manual queue item")


@router.patch("/{queue_item_id}/execute", response_model=MessageResponse)
def execute_queue_item(
    queue_item_id: int,
    payload: QueueExecuteRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    try:
        validate_user_exists(db, payload.executed_by_user_id, "executed_by_user_id")
        item = db.get(QueueItem, queue_item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue item not found")
        if item.status == "executed":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Queue item already executed")

        today = date.today()

        if item.action_type == "assign":
            canonical_employee_id = resolve_canonical_employee_id(db, item.employee_id)
            item.employee_id = canonical_employee_id
            emp_ids = resolve_employee_ids(db, canonical_employee_id)
            existing_active = find_active_allocation_id(db, emp_ids, item.platform_id)
            if existing_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This employee already has this license assigned.",
                )

            source_req = db.get(LicenseRequest, item.source_id) if item.source_id else None
            if source_req and source_req.employee_id != canonical_employee_id:
                source_req.employee_id = canonical_employee_id
            resolved_project_id, resolved_account_id = resolve_assignment_scope(
                db,
                employee_id=canonical_employee_id,
                source_project_id=source_req.project_id if source_req else None,
                source_account_id=source_req.account_id if source_req else None,
                fallback_project_id=item.project_id,
            )
            create_assignment_allocation(
                db,
                employee_id=canonical_employee_id,
                platform_id=item.platform_id,
                project_id=resolved_project_id,
                account_id=resolved_account_id,
                effective_date=(source_req.effective_date if source_req and source_req.effective_date else today),
                monthly_cost=item.cost_snapshot_monthly,
                changed_by_user_id=payload.executed_by_user_id,
                notes=payload.execution_notes,
            )

        elif item.action_type == "revoke":
            resolved_alerts = 0
            allocation, resolved_alerts = revoke_active_allocation(
                db,
                employee_lookup_ids=resolve_employee_ids(db, item.employee_id),
                employee_id_for_alerts=item.employee_id,
                platform_id=item.platform_id,
                revoked_date=today,
                changed_by_user_id=payload.executed_by_user_id,
                notes=payload.execution_notes,
            )
            if allocation is None:
                existing_notes = payload.execution_notes or item.execution_notes or ""
                payload.execution_notes = (
                    (existing_notes + " | ") if existing_notes else ""
                ) + "Closed from queue: no active allocation remained to revoke."
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported queue action type")

        item.status = "executed"
        item.executed_by_user_id = payload.executed_by_user_id
        item.executed_at = datetime.utcnow()
        item.execution_notes = payload.execution_notes

        if item.source_type == "request" and item.source_id:
            source_request = db.get(LicenseRequest, item.source_id)
            if source_request:
                source_request.approval_status = "executed"

        db.commit()

        # Send email notification (non-blocking)
        # DISABLED FOR TESTING - Email notifications are disabled
        # TODO: Re-enable for production
        pass
        # try:
        #     emp = db.get(Employee, item.employee_id) if item.employee_id else None
        #     plat = db.get(Platform, item.platform_id) if item.platform_id else None
        #     proj = db.get(Project, item.project_id) if item.project_id else None
        #     emp_name = emp.full_name if emp else f"Employee #{item.employee_id}"
        #     plat_name = plat.name if plat else f"Platform #{item.platform_id}"
        #     proj_name = proj.name if proj else None
        #     # Look up employee and requester emails from Aspire.
        #     # For Aspire-only employees, employee_id itself is the staff ID.
        #     emp_email = None
        #     requester_email = None
        #     emp_staffid = str(emp.employee_code if emp else item.employee_id).strip() if item.employee_id else None
        #     try:
        #         from app.core.aspire_database import AspireSessionLocal
        #         from app.models.aspire import AspireEmployee
        #         adb = AspireSessionLocal()
        #         try:
        #             if emp_staffid:
        #                 asp_target = adb.scalars(
        #                     select(AspireEmployee).where(
        #                         func.rtrim(AspireEmployee.emp_staffid) == emp_staffid
        #                     )
        #                 ).first()
        #                 if asp_target:
        #                     emp_email = asp_target.email
        #                     emp_name = asp_target.full_name or emp_name
        #             if item.source_type == "request" and item.source_id:
        #                 src_req = db.get(LicenseRequest, item.source_id)
        #                 requester_staffid = str(src_req.requested_by_staffid).strip() if src_req and src_req.requested_by_staffid else None
        #                 if requester_staffid:
        #                     asp_req = adb.scalars(
        #                         select(AspireEmployee).where(
        #                             func.rtrim(AspireEmployee.emp_staffid) == requester_staffid
        #                         )
        #                     ).first()
        #                     if asp_req:
        #                         requester_email = asp_req.email
        #         finally:
        #             adb.close()
        #     except Exception:
        #         pass
        #     email_service.notify_request_executed(
        #         action_type=item.action_type,
        #         employee_name=emp_name,
        #         employee_email=emp_email,
        #         platform_name=plat_name,
        #         project_name=proj_name,
        #         executed_by=None,
        #         requester_email=requester_email,
        #     )
        # except Exception as email_exc:
        #     logger.warning("[EMAIL] Notification failed (non-fatal): %s", email_exc)

        action_label = "assigned" if item.action_type == "assign" else "revoked"
        if item.action_type == "revoke" and resolved_alerts:
            return MessageResponse(
                message=f"License {action_label} and queue item marked as executed; resolved {resolved_alerts} open alert(s)"
            )
        return MessageResponse(message=f"License {action_label} and queue item marked as executed")
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "execute queue item")
    except Exception as exc:
        handle_unexpected_error(db, exc, "execute queue item")


class QueueRejectRequest(BaseModel):
    rejected_by_user_id: int | None = None
    rejection_notes: str | None = None


@router.patch("/{queue_item_id}/reject", response_model=MessageResponse)
def reject_queue_item(
    queue_item_id: int,
    payload: QueueRejectRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    try:
        validate_user_exists(db, payload.rejected_by_user_id, "rejected_by_user_id")
        item = db.get(QueueItem, queue_item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue item not found")
        if item.status in ("executed", "rejected"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Queue item already {item.status}")

        item.status = "rejected"
        item.executed_by_user_id = payload.rejected_by_user_id
        item.executed_at = datetime.utcnow()
        item.execution_notes = payload.rejection_notes

        if item.source_type == "request" and item.source_id:
            source_request = db.get(LicenseRequest, item.source_id)
            if source_request:
                source_request.approval_status = "rejected"

        db.commit()
        return MessageResponse(message="Queue item rejected")
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "reject queue item")
    except Exception as exc:
        handle_unexpected_error(db, exc, "reject queue item")
