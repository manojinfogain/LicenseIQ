"""
Phase 3 integration service for request lifecycle operations.

Uses stored procedures when Phase 3 is enabled and falls back to the existing
ORM implementation only when the feature flag is disabled. For write operations,
SP failures are raised instead of retried through ORM to avoid double mutations.
"""

import logging
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.feature_flags import is_phase3_request_enabled, log_sp_usage, Phase3SPError
from app.models.license import LicenseRequest, ApprovalHistory
from app.schemas.request import LicenseRequestCreate
from app.services.phase3_sp_wrappers import (
    create_license_request as sp_create_license_request,
    approve_license_request as sp_approve_license_request,
    final_approve_license_request as sp_final_approve_license_request,
    reject_license_request as sp_reject_license_request,
)

logger = logging.getLogger(__name__)


def _create_license_request_orm(db: Session, payload: LicenseRequestCreate) -> LicenseRequest:
    """Create license request using ORM."""
    request = LicenseRequest(
        request_type=payload.request_type,
        employee_id=payload.employee_id,
        platform_id=payload.platform_id,
        project_id=payload.project_id,
        account_id=payload.account_id,
        requested_by_user_id=payload.requested_by_user_id,
        requested_by_staffid=payload.requested_by_staffid,
        justification=payload.justification,
        effective_date=payload.effective_date,
        approval_status="submitted",
        approval_stage="pending_account_owner",
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def _approve_license_request_orm(
    db: Session,
    request_id: int,
    approver_user_id: int,
    approver_role: str,
    approval_notes: str | None = None,
    action: str = "approved",
) -> LicenseRequest:
    """Approve license request using ORM (first-level approval)."""
    request = db.get(LicenseRequest, request_id)
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License request not found")

    if request.approval_status in ("approved", "rejected"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request already finalized")

    # Record approval history
    history = ApprovalHistory(
        request_id=request_id,
        approval_stage=request.approval_stage,
        approver_user_id=approver_user_id,
        approver_role=approver_role,
        action=action,
        notes=approval_notes,
    )
    db.add(history)

    # Update request based on action
    if action == "rejected":
        request.approval_status = "rejected"
    elif action == "approved":
        request.approval_stage = "pending_it_admin"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action")

    request.last_approver_user_id = approver_user_id
    request.approval_notes = approval_notes

    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def _final_approve_license_request_orm(
    db: Session,
    request_id: int,
    approver_user_id: int,
    approver_role: str,
    approval_notes: str | None = None,
    action: str = "approved",
) -> LicenseRequest:
    """Final approval of license request using ORM (IT admin stage)."""
    from app.models.license import LicenseAllocation

    request = db.get(LicenseRequest, request_id)
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License request not found")

    if request.approval_stage != "pending_it_admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request is not at IT admin approval stage")

    # Record approval history
    history = ApprovalHistory(
        request_id=request_id,
        approval_stage=request.approval_stage,
        approver_user_id=approver_user_id,
        approver_role=approver_role,
        action=action,
        notes=approval_notes,
    )
    db.add(history)

    # Update request based on action
    if action == "rejected":
        request.approval_status = "rejected"
        request.approval_stage = "rejected"
    elif action == "approved":
        # Create the license allocation
        allocation = LicenseAllocation(
            employee_id=request.employee_id,
            platform_id=request.platform_id,
            project_id=request.project_id,
            account_id=request.account_id,
            status="active",
            effective_date=request.effective_date,
            source_type="request_approved",
        )
        db.add(allocation)

        request.approval_status = "approved"
        request.approval_stage = "approved"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action")

    request.last_approver_user_id = approver_user_id
    request.approval_notes = approval_notes

    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def _reject_license_request_orm(
    db: Session,
    request_id: int,
    rejecter_user_id: int,
    rejecter_role: str,
    rejection_reason: str,
) -> LicenseRequest:
    """Reject license request using ORM."""
    request = db.get(LicenseRequest, request_id)
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License request not found")

    if request.approval_status in ("approved", "rejected"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request already finalized")

    # Record rejection in approval history
    history = ApprovalHistory(
        request_id=request_id,
        approval_stage=request.approval_stage,
        approver_user_id=rejecter_user_id,
        approver_role=rejecter_role,
        action="rejected",
        notes=rejection_reason,
    )
    db.add(history)

    # Update request status to rejected
    request.approval_status = "rejected"
    request.approval_stage = "rejected"
    request.last_approver_user_id = rejecter_user_id
    request.approval_notes = rejection_reason

    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def create_license_request_phase3(db: Session, payload: LicenseRequestCreate) -> LicenseRequest:
    """Create license request using Phase 3 SP when enabled, ORM otherwise."""
    if is_phase3_request_enabled():
        try:
            log_sp_usage("create_license_request", True)
            request_id = sp_create_license_request(
                db,
                request_type=payload.request_type,
                employee_id=payload.employee_id,
                platform_id=payload.platform_id,
                project_id=payload.project_id,
                account_id=payload.account_id,
                requested_by_user_id=payload.requested_by_user_id,
                requested_by_staffid=payload.requested_by_staffid,
                justification=payload.justification,
                effective_date=payload.effective_date,
            )
            if not request_id:
                raise Phase3SPError("Request creation returned no ID")

            request = db.get(LicenseRequest, request_id)
            if not request:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Request creation failed")
            return request
        except HTTPException:
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Phase 3 SP failed for create request")
            raise Phase3SPError("Phase 3 create request failed") from exc

    log_sp_usage("create_license_request", False)
    return _create_license_request_orm(db, payload)


def approve_license_request_phase3(
    db: Session,
    request_id: int,
    approver_user_id: int,
    approver_role: str,
    approval_notes: str | None = None,
    action: str = "approved",
) -> LicenseRequest:
    """Approve license request using Phase 3 SP when enabled, ORM otherwise."""
    if is_phase3_request_enabled():
        try:
            log_sp_usage("approve_license_request", True)
            sp_approve_license_request(
                db,
                request_id=request_id,
                approver_user_id=approver_user_id,
                approver_role=approver_role,
                approval_notes=approval_notes,
                action=action,
            )
            # Expire the session to force reload from database
            db.expire_all()
            request = db.get(LicenseRequest, request_id)
            if not request:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License request not found")
            return request
        except HTTPException:
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Phase 3 SP failed for approve request")
            raise Phase3SPError("Phase 3 approve request failed") from exc

    log_sp_usage("approve_license_request", False)
    return _approve_license_request_orm(
        db,
        request_id=request_id,
        approver_user_id=approver_user_id,
        approver_role=approver_role,
        approval_notes=approval_notes,
        action=action,
    )


def final_approve_license_request_phase3(
    db: Session,
    request_id: int,
    approver_user_id: int,
    approver_role: str,
    approval_notes: str | None = None,
    action: str = "approved",
) -> LicenseRequest:
    """Final approval of license request using Phase 3 SP when enabled, ORM otherwise."""
    if is_phase3_request_enabled():
        try:
            log_sp_usage("final_approve_license_request", True)
            sp_final_approve_license_request(
                db,
                request_id=request_id,
                approver_user_id=approver_user_id,
                approver_role=approver_role,
                approval_notes=approval_notes,
                action=action,
            )
            # Expire the session to force reload from database
            db.expire_all()
            request = db.get(LicenseRequest, request_id)
            if not request:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License request not found")
            return request
        except HTTPException:
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Phase 3 SP failed for final approve request")
            raise Phase3SPError("Phase 3 final approve request failed") from exc

    log_sp_usage("final_approve_license_request", False)
    return _final_approve_license_request_orm(
        db,
        request_id=request_id,
        approver_user_id=approver_user_id,
        approver_role=approver_role,
        approval_notes=approval_notes,
        action=action,
    )


def reject_license_request_phase3(
    db: Session,
    request_id: int,
    rejecter_user_id: int,
    rejecter_role: str,
    rejection_reason: str,
) -> LicenseRequest:
    """Reject license request using Phase 3 SP when enabled, ORM otherwise."""
    if is_phase3_request_enabled():
        try:
            log_sp_usage("reject_license_request", True)
            sp_reject_license_request(
                db,
                request_id=request_id,
                rejecter_user_id=rejecter_user_id,
                rejecter_role=rejecter_role,
                rejection_reason=rejection_reason,
            )
            # Expire the session to force reload from database
            db.expire_all()
            request = db.get(LicenseRequest, request_id)
            if not request:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License request not found")
            return request
        except HTTPException:
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Phase 3 SP failed for reject request")
            raise Phase3SPError("Phase 3 reject request failed") from exc

    log_sp_usage("reject_license_request", False)
    return _reject_license_request_orm(
        db,
        request_id=request_id,
        rejecter_user_id=rejecter_user_id,
        rejecter_role=rejecter_role,
        rejection_reason=rejection_reason,
    )
