-- Phase 4: Queue Execution & Alerts Stored Procedures
-- 6 procedures for complete queue processing and alert management
-- Transactional operations for assignment execution, revocation, and alert lifecycle

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- ============================================================================
-- usp_ExecuteQueueItemAssignment: Execute license assignment from queue
-- ============================================================================
CREATE OR ALTER PROCEDURE usp_ExecuteQueueItemAssignment
    @QueueItemId INT,
    @ExecutedByUserId INT,
    @ExecutionNotes NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;
        
        -- Get queue item details
        DECLARE @SourceType NVARCHAR(30), @SourceId INT, @EmployeeId INT, @PlatformId INT, 
                @ProjectId INT, @AccountId INT, @CostSnapshot NUMERIC(12, 2), @EffectiveDate DATE;
        
        SELECT @SourceType = source_type, @SourceId = source_id, @EmployeeId = employee_id,
               @PlatformId = platform_id, @ProjectId = project_id, @AccountId = NULL,
               @CostSnapshot = cost_snapshot_monthly, @EffectiveDate = CAST(GETUTCDATE() AS DATE)
        FROM queue_items WHERE id = @QueueItemId;
        
        IF @EmployeeId IS NULL
            THROW 50001, 'Queue item not found', 1;
        
        -- Verify employee and platform exist
        IF NOT EXISTS (SELECT 1 FROM employees WHERE id = @EmployeeId)
            THROW 50002, 'Employee not found', 1;
        
        IF NOT EXISTS (SELECT 1 FROM platforms WHERE id = @PlatformId)
            THROW 50003, 'Platform not found', 1;
        
        -- Check for existing active allocation
        IF EXISTS (SELECT 1 FROM license_allocations 
                   WHERE employee_id = @EmployeeId AND platform_id = @PlatformId AND status = 'active')
            THROW 50004, 'Active allocation already exists for this employee and platform', 1;
        
        -- Create the license allocation
        INSERT INTO license_allocations 
            (employee_id, platform_id, project_id, account_id, status, effective_date, monthly_cost, source_type)
        VALUES 
            (@EmployeeId, @PlatformId, @ProjectId, @AccountId, 'active', @EffectiveDate, @CostSnapshot, 'queue_executed');
        
        -- Mark queue item as executed
        UPDATE queue_items
        SET status = 'executed', executed_by_user_id = @ExecutedByUserId, executed_at = GETUTCDATE(), 
            execution_notes = @ExecutionNotes
        WHERE id = @QueueItemId;
        
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
-- usp_ExecuteQueueItemRevocation: Execute license revocation from queue
-- ============================================================================
CREATE OR ALTER PROCEDURE usp_ExecuteQueueItemRevocation
    @QueueItemId INT,
    @ExecutedByUserId INT,
    @ExecutionNotes NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;
        
        -- Get queue item details
        DECLARE @EmployeeId INT, @PlatformId INT, @AllocationId INT;
        
        SELECT @EmployeeId = employee_id, @PlatformId = platform_id
        FROM queue_items WHERE id = @QueueItemId;
        
        IF @EmployeeId IS NULL
            THROW 50001, 'Queue item not found', 1;
        
        -- Find the active allocation — use most recently created to handle multiple active rows
        SELECT TOP 1 @AllocationId = id
        FROM license_allocations
        WHERE employee_id = @EmployeeId AND platform_id = @PlatformId AND status = 'active'
        ORDER BY id DESC;
        
        IF @AllocationId IS NULL
            THROW 50005, 'No active allocation found for this employee and platform', 1;
        
        -- Mark allocation as revoked
        UPDATE license_allocations
        SET status = 'revoked', revoked_date = CAST(GETUTCDATE() AS DATE)
        WHERE id = @AllocationId;
        
        -- Record the audit
        INSERT INTO allocation_audits (allocation_id, event_type, event_source, old_status, new_status, 
                                       changed_by_user_id, changed_at, notes)
        VALUES (@AllocationId, 'revocation', 'queue_executed', 'active', 'revoked', @ExecutedByUserId, GETUTCDATE(), @ExecutionNotes);
        
        -- Mark queue item as executed
        UPDATE queue_items
        SET status = 'executed', executed_by_user_id = @ExecutedByUserId, executed_at = GETUTCDATE(),
            execution_notes = @ExecutionNotes
        WHERE id = @QueueItemId;
        
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
-- usp_MarkQueueItemExecuted: Mark queue item as executed
-- ============================================================================
CREATE OR ALTER PROCEDURE usp_MarkQueueItemExecuted
    @QueueItemId INT,
    @ExecutedByUserId INT,
    @ExecutionNotes NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        -- Validate queue item exists
        IF NOT EXISTS (SELECT 1 FROM queue_items WHERE id = @QueueItemId)
            THROW 50001, 'Queue item not found', 1;
        
        -- Validate user exists
        IF @ExecutedByUserId IS NOT NULL AND NOT EXISTS (SELECT 1 FROM users WHERE id = @ExecutedByUserId)
            THROW 50002, 'User not found', 1;
        
        -- Mark queue item as executed
        UPDATE queue_items
        SET status = 'executed', executed_by_user_id = @ExecutedByUserId, executed_at = GETUTCDATE(),
            execution_notes = @ExecutionNotes
        WHERE id = @QueueItemId;
        
    END TRY
    BEGIN CATCH
        THROW;
    END CATCH
END;
GO

-- ============================================================================
-- usp_CreateAlert: Create a new alert
-- ============================================================================
CREATE OR ALTER PROCEDURE usp_CreateAlert
    @EmployeeId INT = NULL,
    @PlatformId INT = NULL,
    @AlertType NVARCHAR(50),
    @Priority NVARCHAR(20),
    @Reason NVARCHAR(255),
    @Detail NVARCHAR(MAX) = NULL,
    @SourceSystem NVARCHAR(50) = 'manual',
    @CreatedAlertId INT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;
        
        -- Create the alert
        INSERT INTO alerts (employee_id, platform_id, alert_type, priority, source_system, reason, detail, status, created_at)
        VALUES (@EmployeeId, @PlatformId, @AlertType, @Priority, @SourceSystem, @Reason, @Detail, 'open', GETUTCDATE());
        
        SET @CreatedAlertId = SCOPE_IDENTITY();
        
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
-- usp_ResolveAlert: Mark alert as resolved
-- ============================================================================
CREATE OR ALTER PROCEDURE usp_ResolveAlert
    @AlertId INT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        -- Validate alert exists
        IF NOT EXISTS (SELECT 1 FROM alerts WHERE id = @AlertId)
            THROW 50001, 'Alert not found', 1;
        
        -- Mark alert as resolved
        UPDATE alerts
        SET status = 'resolved', resolved_at = GETUTCDATE()
        WHERE id = @AlertId;
        
    END TRY
    BEGIN CATCH
        THROW;
    END CATCH
END;
GO

-- ============================================================================
-- usp_GetQueueMetrics: Get queue performance metrics
-- ============================================================================
CREATE OR ALTER PROCEDURE usp_GetQueueMetrics
    @StartDate DATE = NULL,
    @EndDate DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        -- Use default date range if not provided
        DECLARE @ActualStartDate DATE, @ActualEndDate DATE;
        SET @ActualStartDate = ISNULL(@StartDate, CAST(DATEADD(DAY, -30, GETUTCDATE()) AS DATE));
        SET @ActualEndDate = ISNULL(@EndDate, CAST(GETUTCDATE() AS DATE));
        
        -- Return metrics
        SELECT 
            (SELECT COUNT(*) FROM queue_items WHERE status = 'pending' AND created_at >= @ActualStartDate) AS pending_count,
            (SELECT COUNT(*) FROM queue_items WHERE status = 'executed' AND executed_at >= @ActualStartDate AND executed_at < DATEADD(DAY, 1, @ActualEndDate)) AS executed_count,
            (SELECT COUNT(*) FROM queue_items WHERE status = 'rejected' AND created_at >= @ActualStartDate) AS rejected_count,
            (SELECT COUNT(*) FROM alerts WHERE status = 'open' AND created_at >= @ActualStartDate) AS open_alerts,
            (SELECT COUNT(*) FROM alerts WHERE status = 'resolved' AND resolved_at >= @ActualStartDate AND resolved_at < DATEADD(DAY, 1, @ActualEndDate)) AS resolved_alerts,
            (SELECT AVG(DATEDIFF(MINUTE, created_at, executed_at)) 
             FROM queue_items WHERE status = 'executed' AND executed_at >= @ActualStartDate AND executed_at < DATEADD(DAY, 1, @ActualEndDate)) AS avg_queue_time_minutes;
        
    END TRY
    BEGIN CATCH
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
WHERE ROUTINE_NAME IN ('usp_ExecuteQueueItemAssignment', 'usp_ExecuteQueueItemRevocation', 'usp_MarkQueueItemExecuted', 
                       'usp_CreateAlert', 'usp_ResolveAlert', 'usp_GetQueueMetrics')
ORDER BY ROUTINE_NAME;
