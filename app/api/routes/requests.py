from fastapi import APIRouter, Depends, HTTPException, Query, status
from datetime import datetime, date
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload
from pydantic import BaseModel
import logging

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
from app.models.license import LicenseAllocation, LicenseRequest, QueueItem, ApprovalHistory, AllocationAudit, Alert
from app.models.organization import Employee, Project, Account
from app.models.platform import Platform
from app.schemas.request import LicenseRequestCreate, LicenseRequestRead
from app.services.employee_resolution import resolve_canonical_employee_id
from app.services.license_execution import (
    create_assignment_allocation,
    resolve_assignment_scope,
    revoke_active_allocation,
)
from app.services.pricing import calculate_platform_monthly_unit_cost_for_platform
from app.services.approval_workflow import determine_initial_approval_stage, create_queue_item_for_request
from app.services import email as email_service
from app.services.phase1_integration import get_license_requests_phase1

logger = logging.getLogger(__name__)

router = APIRouter()


class ApprovalAction(BaseModel):
    """Schema for approval actions"""
    action: str  # "approved" or "rejected"
    notes: str | None = None


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
            detail="This employee does not have an active license for the selected platform.",
        )

    pending_revoke_request = find_pending_request_id(db, emp_ids, platform_id, "revoke")
    if pending_revoke_request:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A revoke request for this employee and license is already pending.",
        )

    pending_queue_item = find_pending_queue_item_id(db, emp_ids, platform_id, "revoke")
    if pending_queue_item:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This license is already pending revocation for the selected employee.",
        )


@router.get("", response_model=list[LicenseRequestRead])
def list_requests(staffid: str | None = None, db: Session = Depends(get_db)) -> list[LicenseRequestRead]:
    try:
        if staffid:
            staffid = staffid.strip()
            logger.info(f"[LIST_REQUESTS] Filtering by staffid='{staffid}'")
            # Use Phase 1 SP if enabled, ORM fallback
            request_dicts = get_license_requests_phase1(db, staff_id=staffid)
        else:
            logger.info("[LIST_REQUESTS] No staffid provided, returning all requests")
            # Use Phase 1 SP if enabled, ORM fallback
            request_dicts = get_license_requests_phase1(db)
        
        # Convert dicts back to ORM objects for response serialization
        requests = []
        for req_dict in request_dicts:
            req = db.get(LicenseRequest, req_dict["id"])
            if req:
                requests.append(req)
        
        logger.info(f"[LIST_REQUESTS] Query complete - Found {len(requests)} requests")
        return requests
    except SQLAlchemyError as exc:
        logger.error(f"[LIST_REQUESTS] SQLAlchemy error: {str(exc)}")
        handle_database_error(db, exc, "list requests")
    except Exception as exc:
        logger.error(f"[LIST_REQUESTS] Exception: {str(exc)}", exc_info=True)
        handle_unexpected_error(db, exc, "list requests")


@router.post("", response_model=LicenseRequestRead, status_code=status.HTTP_201_CREATED)
def create_request(payload: LicenseRequestCreate, db: Session = Depends(get_db)) -> LicenseRequestRead:
    logger.info("[CREATE_REQUEST] Employee ID=%s Platform ID=%s", payload.employee_id, payload.platform_id)
    try:
        validate_user_exists(db, payload.requested_by_user_id, "requested_by_user_id")
        canonical_employee_id = resolve_canonical_employee_id(db, payload.employee_id)
        employee = db.get(Employee, canonical_employee_id)
        platform_stmt = select(Platform).where(Platform.id == payload.platform_id).options(selectinload(Platform.contracts))
        platform = db.scalar(platform_stmt)

        if not platform:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")

        if payload.request_type == "assign":
            _ensure_assign_not_duplicated(db, canonical_employee_id, payload.platform_id)
        elif payload.request_type == "revoke":
            _ensure_revoke_is_valid(db, canonical_employee_id, payload.platform_id)

        try:
            cost_snapshot = calculate_platform_monthly_unit_cost_for_platform(db, platform)
        except Exception as exc:
            logger.warning("Failed to calculate cost snapshot for request: %s", exc)
            cost_snapshot = 0

        # Create the request record
        record = LicenseRequest(
            request_type=payload.request_type,
            employee_id=canonical_employee_id,
            platform_id=payload.platform_id,
            project_id=payload.project_id or (employee.project_id if employee else None),
            account_id=payload.account_id or (employee.account_id if employee else None),
            requested_by_user_id=payload.requested_by_user_id,
            requested_by_staffid=payload.requested_by_staffid,
            justification=payload.justification,
            effective_date=payload.effective_date,
            approval_status="submitted",
        )
        logger.info(f"[CREATE_REQUEST] Created request with staffid: {payload.requested_by_staffid}")
        db.add(record)
        db.flush()

        # Determine initial approval stage based on requester role
        approval_stage, assigned_to_user_id = determine_initial_approval_stage(
            db, record, payload.requested_by_staffid or ""
        )
        
        # Update request with approval stage
        record.approval_stage = "pending_it_admin" if approval_stage == "self_approved" else approval_stage
        if approval_stage == "self_approved":
            record.approval_status = "pending_it_admin"
        else:
            record.approval_status = "pending_approval"
        
        db.flush()
        
        # Create queue item with approval stage information
        queue_item = create_queue_item_for_request(
            db, record, approval_stage, assigned_to_user_id, cost_snapshot
        )
        db.add(queue_item)
        
        # If self-approved, create approval history record
        if approval_stage == "self_approved":
            approval_history = ApprovalHistory(
                request_id=record.id,
                approval_stage="self_approved",
                approver_user_id=payload.requested_by_user_id,
                approver_role="self",
                action="approved",
                notes="Self-approved by authorized role"
            )
            db.add(approval_history)

        db.commit()
        db.refresh(record)

        # Send email notification (non-blocking)
        # DISABLED FOR TESTING - Email notifications are disabled
        # TODO: Re-enable for production
        pass
        # try:
        #     emp_name = employee.full_name if employee else f"Employee #{payload.employee_id}"
        #     proj = db.get(Project, record.project_id) if record.project_id else None
        #     acct = db.get(Account, record.account_id) if record.account_id else None
        #     # Look up both employee and requester emails from Aspire.
        #     emp_email = None
        #     requester_email = None
        #     requester_name = None
        #     emp_staffid = str(employee.employee_code if employee else payload.employee_id).strip()
        #     requester_staffid = str(payload.requested_by_staffid).strip() if payload.requested_by_staffid else None
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
        #             if requester_staffid:
        #                 asp_req = adb.scalars(
        #                     select(AspireEmployee).where(
        #                         func.rtrim(AspireEmployee.emp_staffid) == requester_staffid
        #                     )
        #                 ).first()
        #                 if asp_req:
        #                     requester_email = asp_req.email
        #                     requester_name = asp_req.full_name
        #         finally:
        #             adb.close()
        #     except Exception:
        #         pass
        #     
        #     # Notify appropriate approver based on approval stage
        #     if approval_stage == "self_approved":
        #         email_service.notify_request_raised(
        #             request_type=record.request_type,
        #             employee_name=emp_name,
        #             employee_email=emp_email,
        #             platform_name=platform.name,
        #             project_name=proj.name if proj else getattr(payload, 'project_name', None),
        #             account_name=acct.name if acct else getattr(payload, 'account_name', None),
        #             requester_name=requester_name,
        #             requester_email=requester_email,
        #             effective_date=str(record.effective_date) if record.effective_date else None,
        #             is_self_approved=True,
        #         )
        #     elif assigned_to_user_id:
        #         # Notify account owner
        #         email_service.notify_request_needs_approval(
        #             request_id=record.id,
        #             employee_name=emp_name,
        #             platform_name=platform.name,
        #             approver_role="account_owner",
        #             assigned_to_user_id=assigned_to_user_id,
        #         )
        # except Exception as email_exc:
        #     logger.warning("[EMAIL] Notification failed (non-fatal): %s", email_exc)

        return record
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "create request")
    except Exception as exc:
        handle_unexpected_error(db, exc, "create request")


@router.post("/{request_id}/approve", response_model=LicenseRequestRead)
def approve_request(
    request_id: int,
    approval: ApprovalAction,
    db: Session = Depends(get_db)
) -> LicenseRequestRead:
    """
    Approve or reject a request at current approval stage.
    Only authorized approvers (Account Owner for pending_account_owner, IT Admin for pending_it_admin) can approve.
    """
    logger.info("[APPROVE_REQUEST] Request ID=%s Action=%s", request_id, approval.action)
    try:
        request = db.get(LicenseRequest, request_id)
        if not request:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
        
        if approval.action not in ["approved", "rejected"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action must be 'approved' or 'rejected'"
            )
        
        # For now, we'll assume the current user is authorized
        # In production, you'd verify the user's role and scope
        from app.services.approval_workflow import approve_request_at_stage
        
        approver_user_id = None  # TODO: Get from current user context
        approver_role = None  # TODO: Determine based on current stage and user role
        
        if request.approval_stage == "pending_account_owner":
            approver_role = "account_owner"
        elif request.approval_stage == "pending_it_admin":
            approver_role = "admin"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Request is in '{request.approval_stage}' stage and cannot be approved or rejected"
            )
        
        # Record the approval action
        approval_record = ApprovalHistory(
            request_id=request.id,
            approval_stage=request.approval_stage,
            approver_user_id=approver_user_id,
            approver_role=approver_role,
            action=approval.action,
            notes=approval.notes
        )
        db.add(approval_record)
        
        if approval.action == "rejected":
            request.approval_stage = "rejected"
            request.approval_status = "rejected"
            request.last_approver_user_id = approver_user_id
            request.approval_notes = approval.notes
            
            # Update queue item
            queue_item = db.scalar(
                select(QueueItem)
                .where(QueueItem.source_type == "request")
                .where(QueueItem.source_id == request.id)
            )
            if queue_item:
                queue_item.status = "rejected"
                queue_item.executed_by_user_id = approver_user_id
                queue_item.execution_notes = approval.notes
        else:
            # Approved
            if request.approval_stage == "pending_account_owner":
                # Move to IT Admin approval
                request.approval_stage = "pending_it_admin"
                request.approval_status = "pending_it_admin"
                request.last_approver_user_id = approver_user_id
                request.last_approval_time = datetime.utcnow()
                
                # Update queue item
                queue_item = db.scalar(
                    select(QueueItem)
                    .where(QueueItem.source_type == "request")
                    .where(QueueItem.source_id == request.id)
                )
                if queue_item:
                    queue_item.approval_stage = "pending_it_admin"
                    queue_item.assigned_approval_role = "it_admin"
            
            elif request.approval_stage == "pending_it_admin":
                # Final approval by IT Admin — approve AND execute immediately
                # Uses the EXACT same logic as the "Mark executed" button
                today = date.today()

                queue_item = db.scalar(
                    select(QueueItem)
                    .where(QueueItem.source_type == "request")
                    .where(QueueItem.source_id == request.id)
                )

                if request.request_type == "assign":
                    canonical_employee_id = resolve_canonical_employee_id(db, request.employee_id)
                    request.employee_id = canonical_employee_id
                    if queue_item and queue_item.employee_id != canonical_employee_id:
                        queue_item.employee_id = canonical_employee_id

                    emp_ids = resolve_employee_ids(db, canonical_employee_id)
                    existing_active = find_active_allocation_id(
                        db, emp_ids, request.platform_id
                    )
                    if not existing_active:
                        resolved_project_id, resolved_account_id = resolve_assignment_scope(
                            db,
                            employee_id=canonical_employee_id,
                            source_project_id=request.project_id,
                            source_account_id=request.account_id,
                            fallback_project_id=queue_item.project_id if queue_item else None,
                        )
                        create_assignment_allocation(
                            db,
                            employee_id=canonical_employee_id,
                            platform_id=request.platform_id,
                            project_id=resolved_project_id,
                            account_id=resolved_account_id,
                            effective_date=request.effective_date or today,
                            monthly_cost=queue_item.cost_snapshot_monthly if queue_item else None,
                            changed_by_user_id=approver_user_id,
                            notes=approval.notes,
                        )
                        logger.info(
                            "[APPROVE_REQUEST] Created allocation employee_id=%s platform_id=%s",
                            canonical_employee_id,
                            request.platform_id,
                        )
                    else:
                        logger.info(
                            "[APPROVE_REQUEST] Skipped duplicate allocation employee_id=%s platform_id=%s",
                            canonical_employee_id,
                            request.platform_id,
                        )

                elif request.request_type == "revoke":
                    _, resolved_alerts = revoke_active_allocation(
                        db,
                        employee_lookup_ids={request.employee_id},
                        employee_id_for_alerts=request.employee_id,
                        platform_id=request.platform_id,
                        revoked_date=today,
                        changed_by_user_id=approver_user_id,
                        notes=approval.notes,
                    )

                # Mark queue item as executed (just like Mark executed button does)
                if queue_item:
                    queue_item.status = "executed"
                    queue_item.approval_stage = "approved"
                    queue_item.executed_by_user_id = approver_user_id
                    queue_item.executed_at = datetime.utcnow()
                    queue_item.execution_notes = approval.notes

                # Mark request as fully executed
                request.approval_stage = "approved"
                request.approval_status = "executed"
                request.last_approver_user_id = approver_user_id
        
        db.commit()
        db.refresh(request)
        
        logger.info("[APPROVE_REQUEST] Updated request ID=%s to stage=%s", request_id, request.approval_stage)
        
        return request
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "approve request")
    except Exception as exc:
        handle_unexpected_error(db, exc, "approve request")


@router.get("/history")
def list_approval_history(
    staffid: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    """Return the account owner's approval action history (approved/rejected requests) for their account."""
    try:
        from app.models.access import EmployeeWiseRoleMapping
        account_ids: list[int] = []
        if staffid:
            # Find accounts owned by this person via scope_ref_id on their account_owner role mapping
            mappings = list(db.scalars(
                select(EmployeeWiseRoleMapping)
                .join(EmployeeWiseRoleMapping.role)
                .where(EmployeeWiseRoleMapping.emp_staffid == staffid.strip())
                .where(EmployeeWiseRoleMapping.is_active == True)
            ).all())
            for m in mappings:
                if m.role and m.role.code in ("account_owner", "account") and m.scope_ref_id:
                    account_ids.append(m.scope_ref_id)
            # Fallback: use employee's own account_id if no scope mapping found
            if not account_ids:
                emp = db.scalar(select(Employee).where(Employee.employee_code == staffid.strip()))
                if emp and emp.account_id:
                    account_ids.append(emp.account_id)

        stmt = (
            select(LicenseRequest)
            .where(LicenseRequest.approval_stage.in_(["rejected", "pending_it_admin", "approved"]))
        )
        if account_ids:
            stmt = stmt.where(LicenseRequest.account_id.in_(account_ids))

        stmt = stmt.order_by(
            LicenseRequest.last_approval_time.desc(),
            LicenseRequest.created_at.desc(),
        ).limit(limit)

        requests_list = list(db.scalars(stmt).all())

        # employee_id in license_requests stores the Aspire staff ID (not the DB PK)
        # so we must look up by employee_code, not by PK
        all_emp_ids = {str(r.employee_id) for r in requests_list}
        requester_staffids = {r.requested_by_staffid for r in requests_list if r.requested_by_staffid}
        all_codes = all_emp_ids | requester_staffids

        emp_by_code: dict[str, Employee] = {
            e.employee_code: e
            for e in db.scalars(
                select(Employee).where(Employee.employee_code.in_(all_codes))
            ).all()
        }

        result = []
        for req in requests_list:
            emp_obj = emp_by_code.get(str(req.employee_id))
            plat_obj = db.get(Platform, req.platform_id)

            ao_history = db.scalar(
                select(ApprovalHistory)
                .where(ApprovalHistory.request_id == req.id)
                .where(ApprovalHistory.approver_role == "account_owner")
                .order_by(ApprovalHistory.created_at.desc())
            )

            if ao_history:
                action = ao_history.action
                action_date = ao_history.created_at
                notes = ao_history.notes
            else:
                action = "rejected" if req.approval_stage == "rejected" else "approved"
                action_date = req.last_approval_time or req.created_at
                notes = req.approval_notes

            requester_sid = req.requested_by_staffid or ""
            requester_emp = emp_by_code.get(requester_sid.strip()) if requester_sid else None
            requester_name = requester_emp.full_name if requester_emp else (f"Staff {requester_sid}" if requester_sid else "—")

            result.append({
                "request_id": req.id,
                "request_type": req.request_type,
                "employee_name": emp_obj.full_name if emp_obj else f"Employee #{req.employee_id}",
                "employee_id": req.employee_id,
                "platform_name": plat_obj.name if plat_obj else f"Platform #{req.platform_id}",
                "action": action,
                "current_stage": req.approval_stage,
                "current_status": req.approval_status,
                "action_date": action_date.isoformat() if action_date else None,
                "raised_on": req.created_at.isoformat() if req.created_at else None,
                "raised_by": requester_name,
                "notes": notes,
                "requested_by": req.requested_by_staffid,
            })

        return result
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "list approval history")
    except Exception as exc:
        handle_unexpected_error(db, exc, "list approval history")


@router.get("/{request_id}", response_model=LicenseRequestRead)
def get_request(request_id: int, db: Session = Depends(get_db)) -> LicenseRequestRead:
    """Get a specific license request."""
    try:
        request = db.get(LicenseRequest, request_id)
        if not request:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
        return request
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "get request")
    except Exception as exc:
        handle_unexpected_error(db, exc, "get request")
