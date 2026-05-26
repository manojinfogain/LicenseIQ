"""Phase 3 Stored Procedure Wrappers: Request Lifecycle Operations"""

from datetime import date, datetime
from sqlalchemy import text
from sqlalchemy.orm import Session


class Phase3SPError(Exception):
    """Raised when a Phase 3 stored procedure call fails."""


def create_license_request(
    db: Session,
    request_type: str,
    employee_id: int,
    platform_id: int,
    project_id: int | None = None,
    account_id: int | None = None,
    requested_by_user_id: int | None = None,
    requested_by_staffid: str | None = None,
    justification: str | None = None,
    effective_date: date | None = None,
) -> int:
    """
    Execute usp_CreateLicenseRequest stored procedure.
    Returns the ID of the created license request.
    """
    try:
        result = db.execute(
            text(
                """
                DECLARE @CreatedRequestId INT;
                
                EXEC dbo.usp_CreateLicenseRequest
                    @RequestType = :request_type,
                    @EmployeeId = :employee_id,
                    @PlatformId = :platform_id,
                    @ProjectId = :project_id,
                    @AccountId = :account_id,
                    @RequestedByUserId = :requested_by_user_id,
                    @RequestedByStaffId = :requested_by_staffid,
                    @Justification = :justification,
                    @EffectiveDate = :effective_date,
                    @CreatedRequestId = @CreatedRequestId OUTPUT;
                
                SELECT @CreatedRequestId AS request_id;
                """
            ),
            {
                "request_type": request_type,
                "employee_id": employee_id,
                "platform_id": platform_id,
                "project_id": project_id,
                "account_id": account_id,
                "requested_by_user_id": requested_by_user_id,
                "requested_by_staffid": requested_by_staffid,
                "justification": justification,
                "effective_date": effective_date,
            },
        ).fetchone()
        return int(result[0]) if result else None
    except Exception as exc:
        raise Phase3SPError(f"usp_CreateLicenseRequest failed: {exc}") from exc


def approve_license_request(
    db: Session,
    request_id: int,
    approver_user_id: int,
    approver_role: str,
    approval_notes: str | None = None,
    action: str = "approved",
) -> None:
    """
    Execute usp_ApproveLicenseRequest stored procedure.
    First-level approval (account owner stage).
    """
    try:
        db.execute(
            text(
                """
                EXEC dbo.usp_ApproveLicenseRequest
                    @RequestId = :request_id,
                    @ApproverUserId = :approver_user_id,
                    @ApproverRole = :approver_role,
                    @ApprovalNotes = :approval_notes,
                    @Action = :action;
                """
            ),
            {
                "request_id": request_id,
                "approver_user_id": approver_user_id,
                "approver_role": approver_role,
                "approval_notes": approval_notes,
                "action": action,
            },
        )
    except Exception as exc:
        raise Phase3SPError(f"usp_ApproveLicenseRequest failed: {exc}") from exc


def final_approve_license_request(
    db: Session,
    request_id: int,
    approver_user_id: int,
    approver_role: str,
    approval_notes: str | None = None,
    action: str = "approved",
) -> None:
    """
    Execute usp_FinalApproveLicenseRequest stored procedure.
    Final approval (IT admin stage) and allocation creation if approved.
    """
    try:
        db.execute(
            text(
                """
                EXEC dbo.usp_FinalApproveLicenseRequest
                    @RequestId = :request_id,
                    @ApproverUserId = :approver_user_id,
                    @ApproverRole = :approver_role,
                    @ApprovalNotes = :approval_notes,
                    @Action = :action;
                """
            ),
            {
                "request_id": request_id,
                "approver_user_id": approver_user_id,
                "approver_role": approver_role,
                "approval_notes": approval_notes,
                "action": action,
            },
        )
    except Exception as exc:
        raise Phase3SPError(f"usp_FinalApproveLicenseRequest failed: {exc}") from exc


def reject_license_request(
    db: Session,
    request_id: int,
    rejecter_user_id: int,
    rejecter_role: str,
    rejection_reason: str,
) -> None:
    """
    Execute usp_RejectLicenseRequest stored procedure.
    Direct rejection of a license request with reason.
    """
    try:
        db.execute(
            text(
                """
                EXEC dbo.usp_RejectLicenseRequest
                    @RequestId = :request_id,
                    @RejecterUserId = :rejecter_user_id,
                    @RejecterRole = :rejecter_role,
                    @RejectionReason = :rejection_reason;
                """
            ),
            {
                "request_id": request_id,
                "rejecter_user_id": rejecter_user_id,
                "rejecter_role": rejecter_role,
                "rejection_reason": rejection_reason,
            },
        )
    except Exception as exc:
        raise Phase3SPError(f"usp_RejectLicenseRequest failed: {exc}") from exc
