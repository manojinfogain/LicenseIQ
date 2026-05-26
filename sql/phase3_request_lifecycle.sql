-- Phase 3: Request Lifecycle Stored Procedures
-- 4 procedures for complete license request workflow
-- Atomic transactions with approval tracking and audit trail

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- ============================================================================
-- usp_CreateLicenseRequest: Submit a new license request
-- ============================================================================
CREATE OR ALTER PROCEDURE usp_CreateLicenseRequest
    @RequestType NVARCHAR(20),
    @EmployeeId INT,
    @PlatformId INT,
    @ProjectId INT = NULL,
    @AccountId INT = NULL,
    @RequestedByUserId INT = NULL,
    @RequestedByStaffId NVARCHAR(20) = NULL,
    @Justification NVARCHAR(MAX) = NULL,
    @EffectiveDate DATE = NULL,
    @CreatedRequestId INT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;
        
        -- Validate platform exists
        IF NOT EXISTS (SELECT 1 FROM platforms WHERE id = @PlatformId)
            THROW 50001, 'Platform not found', 1;
        
        -- Validate employee exists
        IF NOT EXISTS (SELECT 1 FROM employees WHERE id = @EmployeeId)
            THROW 50002, 'Employee not found', 1;
        
        -- Create the license request (initial approval stage: pending_account_owner)
        INSERT INTO license_requests 
            (request_type, employee_id, platform_id, project_id, account_id, 
             requested_by_user_id, requested_by_staffid, justification, effective_date, 
             approval_status, approval_stage, created_at)
        VALUES 
            (@RequestType, @EmployeeId, @PlatformId, @ProjectId, @AccountId,
             @RequestedByUserId, @RequestedByStaffId, @Justification, @EffectiveDate,
             'submitted', 'pending_account_owner', GETUTCDATE());
        
        SET @CreatedRequestId = SCOPE_IDENTITY();
        
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO

-- ============================================================================
-- usp_ApproveLicenseRequest: First-level approval (account owner)
-- ============================================================================
CREATE OR ALTER PROCEDURE usp_ApproveLicenseRequest
    @RequestId INT,
    @ApproverUserId INT,
    @ApproverRole NVARCHAR(50),
    @ApprovalNotes NVARCHAR(MAX) = NULL,
    @Action NVARCHAR(20) = 'approved'  -- 'approved' or 'rejected'
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;
        
        -- Validate request exists
        IF NOT EXISTS (SELECT 1 FROM license_requests WHERE id = @RequestId)
            THROW 50001, 'License request not found', 1;
        
        -- Validate approver exists
        IF NOT EXISTS (SELECT 1 FROM users WHERE id = @ApproverUserId)
            THROW 50003, 'Approver user not found', 1;
        
        -- Check request is in a valid state for approval
        DECLARE @CurrentStage NVARCHAR(50);
        DECLARE @CurrentStatus NVARCHAR(30);
        SELECT @CurrentStage = approval_stage, @CurrentStatus = approval_status 
        FROM license_requests WHERE id = @RequestId;
        
        IF @CurrentStatus = 'approved' OR @CurrentStatus = 'rejected'
            THROW 50004, 'Request already finalized', 1;
        
        -- Record approval history
        INSERT INTO approval_histories 
            (request_id, approval_stage, approver_user_id, approver_role, action, notes, created_at)
        VALUES 
            (@RequestId, @CurrentStage, @ApproverUserId, @ApproverRole, @Action, @ApprovalNotes, GETUTCDATE());
        
        -- Update request based on action
        IF @Action = 'rejected'
        BEGIN
            UPDATE license_requests
            SET approval_status = 'rejected',
                last_approver_user_id = @ApproverUserId,
                last_approval_time = GETUTCDATE(),
                approval_notes = @ApprovalNotes
            WHERE id = @RequestId;
        END
        ELSE IF @Action = 'approved'
        BEGIN
            -- Move to next approval stage (pending_it_admin)
            UPDATE license_requests
            SET approval_stage = 'pending_it_admin',
                last_approver_user_id = @ApproverUserId,
                last_approval_time = GETUTCDATE(),
                approval_notes = @ApprovalNotes
            WHERE id = @RequestId;
        END
        ELSE
            THROW 50005, 'Invalid action. Use approved or rejected', 1;
        
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO

-- ============================================================================
-- usp_FinalApproveLicenseRequest: Final approval and allocation creation
-- ============================================================================
CREATE OR ALTER PROCEDURE usp_FinalApproveLicenseRequest
    @RequestId INT,
    @ApproverUserId INT,
    @ApproverRole NVARCHAR(50),
    @ApprovalNotes NVARCHAR(MAX) = NULL,
    @Action NVARCHAR(20) = 'approved'  -- 'approved' or 'rejected'
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;
        
        -- Validate request exists and get details
        DECLARE @EmployeeId INT, @PlatformId INT, @ProjectId INT, @AccountId INT, @EffectiveDate DATE;
        SELECT @EmployeeId = employee_id, @PlatformId = platform_id, 
               @ProjectId = project_id, @AccountId = account_id, @EffectiveDate = effective_date
        FROM license_requests WHERE id = @RequestId;
        
        IF @EmployeeId IS NULL
            THROW 50001, 'License request not found', 1;
        
        -- Validate approver exists
        IF NOT EXISTS (SELECT 1 FROM users WHERE id = @ApproverUserId)
            THROW 50003, 'Approver user not found', 1;
        
        -- Check request is pending_it_admin stage
        IF NOT EXISTS (SELECT 1 FROM license_requests WHERE id = @RequestId AND approval_stage = 'pending_it_admin')
            THROW 50006, 'Request is not at IT admin approval stage', 1;
        
        -- Record approval history
        INSERT INTO approval_histories 
            (request_id, approval_stage, approver_user_id, approver_role, action, notes, created_at)
        VALUES 
            (@RequestId, 'pending_it_admin', @ApproverUserId, @ApproverRole, @Action, @ApprovalNotes, GETUTCDATE());
        
        -- Update request based on action
        IF @Action = 'rejected'
        BEGIN
            UPDATE license_requests
            SET approval_status = 'rejected',
                approval_stage = 'rejected',
                last_approver_user_id = @ApproverUserId,
                last_approval_time = GETUTCDATE(),
                approval_notes = @ApprovalNotes
            WHERE id = @RequestId;
        END
        ELSE IF @Action = 'approved'
        BEGIN
            -- Create the license allocation (execute the approval)
            INSERT INTO license_allocations 
                (employee_id, platform_id, project_id, account_id, status, effective_date, source_type)
            VALUES 
                (@EmployeeId, @PlatformId, @ProjectId, @AccountId, 'active', 
                 ISNULL(@EffectiveDate, CAST(GETUTCDATE() AS DATE)), 'request_approved');
            
            -- Update request to approved
            UPDATE license_requests
            SET approval_status = 'approved',
                approval_stage = 'approved',
                last_approver_user_id = @ApproverUserId,
                last_approval_time = GETUTCDATE(),
                approval_notes = @ApprovalNotes
            WHERE id = @RequestId;
        END
        ELSE
            THROW 50005, 'Invalid action. Use approved or rejected', 1;
        
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO

-- ============================================================================
-- usp_RejectLicenseRequest: Direct rejection with reason
-- ============================================================================
CREATE OR ALTER PROCEDURE usp_RejectLicenseRequest
    @RequestId INT,
    @RejecterUserId INT,
    @RejecterRole NVARCHAR(50),
    @RejectionReason NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;
        
        -- Validate request exists
        IF NOT EXISTS (SELECT 1 FROM license_requests WHERE id = @RequestId)
            THROW 50001, 'License request not found', 1;
        
        -- Validate rejecter exists
        IF NOT EXISTS (SELECT 1 FROM users WHERE id = @RejecterUserId)
            THROW 50003, 'Rejecter user not found', 1;
        
        -- Check request is not already finalized
        IF EXISTS (SELECT 1 FROM license_requests WHERE id = @RequestId AND (approval_status = 'approved' OR approval_status = 'rejected'))
            THROW 50004, 'Request already finalized', 1;
        
        -- Get current approval stage for audit record
        DECLARE @CurrentStage NVARCHAR(50);
        SELECT @CurrentStage = approval_stage FROM license_requests WHERE id = @RequestId;
        
        -- Record rejection in approval history
        INSERT INTO approval_histories 
            (request_id, approval_stage, approver_user_id, approver_role, action, notes, created_at)
        VALUES 
            (@RequestId, @CurrentStage, @RejecterUserId, @RejecterRole, 'rejected', @RejectionReason, GETUTCDATE());
        
        -- Update request status to rejected
        UPDATE license_requests
        SET approval_status = 'rejected',
            approval_stage = 'rejected',
            last_approver_user_id = @RejecterUserId,
            last_approval_time = GETUTCDATE(),
            approval_notes = @RejectionReason
        WHERE id = @RequestId;
        
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO

-- Verification query
SELECT 
    ROUTINE_NAME,
    ROUTINE_TYPE,
    CREATED
FROM INFORMATION_SCHEMA.ROUTINES 
WHERE ROUTINE_NAME IN ('usp_CreateLicenseRequest', 'usp_ApproveLicenseRequest', 'usp_FinalApproveLicenseRequest', 'usp_RejectLicenseRequest')
ORDER BY ROUTINE_NAME;
