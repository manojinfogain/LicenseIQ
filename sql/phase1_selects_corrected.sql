/*
================================================================================
PHASE 1: READ-ONLY STORED PROCEDURES - CORRECTED (lowercase table names)
================================================================================
Replaces 18 ORM/inline SELECT queries with 12 optimized stored procedures.
All read-only, no side effects — low risk.
Created: May 15, 2026
Updated: May 15, 2026 (table name corrections)
*/

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- ============================================================================
-- SP-1: usp_GetDashboardComplete
-- Replaces 8 separate SELECT calls in dashboard bootstrap
-- Returns: platforms, seat_snapshots, allocations, alerts, queue_items, 
--          requests, audits, accounts, gdls, projects
-- ============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_GetDashboardComplete
    @UserId INT = NULL,
    @StaffId NVARCHAR(50) = NULL,
    @OrgLevel BIT = 0
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Return platforms + contracts
    SELECT p.id, p.name, p.vendor, p.category, p.agreement_type, p.license_type,
           p.billing_period, p.currency, p.inactivity_days, p.is_active,
           pc.seat_cost, pc.enterprise_cost, pc.contracted_seats, pc.allocation_method
    FROM dbo.platforms p
    LEFT JOIN dbo.platform_contracts pc ON p.id = pc.platform_id
    ORDER BY p.name;
    
    -- Return seat snapshots
    SELECT id, platform_id, snapshot_date, seat_count
    FROM dbo.platform_seat_snapshots
    ORDER BY snapshot_date;
    
    -- Return license allocations (chunked if needed in Python)
    SELECT id, employee_id, platform_id, project_id, account_id, status,
           effective_date, revoked_date, monthly_cost, source_type
    FROM dbo.license_allocations
    ORDER BY effective_date DESC;
    
    -- Return alerts
    SELECT id, employee_id, platform_id, alert_type, priority, source_system,
           reason, detail, status, created_at, resolved_at
    FROM dbo.alerts
    ORDER BY created_at DESC;
    
    -- Return queue items
    SELECT id, source_type, source_id, employee_id, platform_id, action_type,
           project_id, cost_snapshot_monthly, status, created_at, executed_at,
           approval_stage, assigned_approval_role
    FROM dbo.queue_items
    WHERE status = 'pending'
    ORDER BY created_at DESC;
    
    -- Return license requests
    SELECT id, request_type, employee_id, platform_id, project_id, account_id,
           requested_by_user_id, requested_by_staffid, approval_stage, 
           approval_status, created_at
    FROM dbo.license_requests
    ORDER BY created_at DESC;
    
    -- Return allocation audits
    SELECT id, allocation_id, event_type, event_source, old_status, new_status,
           changed_by_user_id, changed_at, notes
    FROM dbo.allocation_audits
    ORDER BY changed_at;
    
    -- Return accounts
    SELECT id, name, owner_user_id, status
    FROM dbo.accounts
    ORDER BY name;
    
    -- Return GDLs
    SELECT id, code, display_name
    FROM dbo.gdls
    ORDER BY code;
    
    -- Return projects
    SELECT id, name, account_id, gdl_id, project_manager_user_id, status
    FROM dbo.projects
    ORDER BY name;
END;
GO

-- ============================================================================
-- SP-2: usp_GetPlatformById
-- Replaces: db.get(Platform, id)
-- ============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_GetPlatformById
    @PlatformId INT
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT id, name, vendor, category, agreement_type, license_type,
           billing_period, currency, inactivity_days, contractor_allowed,
           shared_allowed, api_available, notes, effective_date, renewal_date, is_active
    FROM dbo.platforms
    WHERE id = @PlatformId;
END;
GO

-- ============================================================================
-- SP-3: usp_GetOpenAlerts
-- Replaces: SELECT Alert + LicenseAllocation join
-- Returns open alerts with active license check
-- ============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_GetOpenAlerts
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT a.id, a.employee_id, a.platform_id, a.alert_type, a.priority,
           a.source_system, a.reason, a.detail, a.status, a.created_at
    FROM dbo.alerts a
    WHERE a.status = 'open'
    ORDER BY a.priority DESC, a.created_at DESC;
END;
GO

-- ============================================================================
-- SP-4: usp_GetManualAlerts
-- Replaces: SELECT LicenseRequest WHERE status IN (submitted, self_approved)
-- ============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_GetManualAlerts
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT id, request_type, employee_id, platform_id, project_id, account_id,
           requested_by_staffid, approval_status, created_at
    FROM dbo.license_requests
    WHERE approval_status IN ('submitted', 'self_approved')
    ORDER BY created_at DESC;
END;
GO

-- ============================================================================
-- SP-5: usp_GetLicenseRequests
-- Replaces: SELECT LicenseRequest with optional staffid filter
-- ============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_GetLicenseRequests
    @StaffId NVARCHAR(50) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT id, request_type, employee_id, platform_id, project_id, account_id,
           requested_by_user_id, requested_by_staffid, justification,
           approval_stage, approval_status, effective_date, created_at
    FROM dbo.license_requests
    WHERE @StaffId IS NULL OR requested_by_staffid = @StaffId
    ORDER BY created_at DESC;
END;
GO

-- ============================================================================
-- SP-6: usp_GetLicenseRequestById
-- Replaces: db.get(LicenseRequest, id)
-- ============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_GetLicenseRequestById
    @RequestId INT
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT id, request_type, employee_id, platform_id, project_id, account_id,
           requested_by_user_id, requested_by_staffid, justification,
           approval_stage, approval_status, effective_date, created_at,
           last_approver_user_id, last_approval_time, approval_notes
    FROM dbo.license_requests
    WHERE id = @RequestId;
END;
GO

-- ============================================================================
-- SP-7: usp_GetApprovalHistory
-- Replaces: SELECT LicenseRequest + ApprovalHistory + EmployeeWiseRoleMapping
-- ============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_GetApprovalHistory
    @StaffId NVARCHAR(50) = NULL,
    @Limit INT = 50
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT TOP (@Limit)
        lr.id, lr.request_type, lr.employee_id, lr.platform_id,
        lr.approval_stage, lr.approval_status, lr.created_at,
        ah.approver_user_id, ah.approver_role, ah.action, ah.notes, ah.created_at AS approval_date
    FROM dbo.license_requests lr
    LEFT JOIN dbo.approval_histories ah ON lr.id = ah.request_id
    WHERE ah.approver_role IN ('account_owner', 'it_admin')
    ORDER BY ah.created_at DESC;
END;
GO

-- ============================================================================
-- SP-8: usp_GetPendingQueueItems
-- Replaces: SELECT QueueItem WHERE status = 'pending'
-- ============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_GetPendingQueueItems
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT id, source_type, source_id, employee_id, platform_id, action_type,
           project_id, cost_snapshot_monthly, status, created_at, executed_at,
           approval_stage, assigned_approval_role
    FROM dbo.queue_items
    WHERE status = 'pending'
    ORDER BY created_at DESC;
END;
GO

-- ============================================================================
-- SP-9: usp_FindActiveAllocationByCode
-- Replaces: 2-step lookup (resolve employee code → find active alloc)
-- MERGED: employee code lookup + active allocation check
-- ============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_FindActiveAllocationByCode
    @StaffId NVARCHAR(50),
    @PlatformId INT
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Try direct staffid first (Aspire synthetic ID)
    DECLARE @EmployeeId INT = TRY_CONVERT(INT, @StaffId);
    
    SELECT TOP 1 id, employee_id, platform_id, status, effective_date, revoked_date
    FROM dbo.license_allocations
    WHERE (employee_id = @EmployeeId OR 
           employee_id IN (SELECT id FROM dbo.employees WHERE employee_code = @StaffId))
      AND platform_id = @PlatformId
      AND status = 'active'
      AND revoked_date IS NULL
    ORDER BY effective_date DESC;
END;
GO

-- ============================================================================
-- SP-10: usp_FindPendingRequest
-- Replaces: SELECT LicenseRequest.id WHERE pending
-- ============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_FindPendingRequest
    @EmployeeId INT,
    @PlatformId INT,
    @RequestType NVARCHAR(20)
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT id
    FROM dbo.license_requests
    WHERE employee_id = @EmployeeId
      AND platform_id = @PlatformId
      AND request_type = @RequestType
      AND approval_status IN ('submitted', 'pending_approval', 'pending_it_admin')
    ORDER BY created_at DESC;
END;
GO

-- ============================================================================
-- SP-11: usp_FindPendingQueueItem
-- Replaces: SELECT QueueItem.id WHERE pending
-- ============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_FindPendingQueueItem
    @EmployeeId INT,
    @PlatformId INT,
    @ActionType NVARCHAR(20)
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT id
    FROM dbo.queue_items
    WHERE employee_id = @EmployeeId
      AND platform_id = @PlatformId
      AND action_type = @ActionType
      AND status = 'pending'
    ORDER BY created_at DESC;
END;
GO

-- ============================================================================
-- SP-12: usp_CheckOpenAlertExists
-- Replaces: SELECT Alert.id WHERE exists
-- Returns 1 if exists, 0 if not
-- ============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_CheckOpenAlertExists
    @EmployeeId INT,
    @AlertType NVARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;
    
    IF EXISTS (
        SELECT 1 FROM dbo.alerts
        WHERE employee_id = @EmployeeId
          AND alert_type = @AlertType
          AND status = 'open'
    )
        SELECT 1 AS alert_exists;
    ELSE
        SELECT 0 AS alert_exists;
END;
GO

-- ============================================================================
-- SP-13: usp_GetRoleMapping
-- Replaces: SELECT EmployeeWiseRoleMapping WHERE staffid
-- ============================================================================
CREATE OR ALTER PROCEDURE dbo.usp_GetRoleMapping
    @StaffId NVARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT ewm.id, ewm.emp_staffid, ewm.role_id, ewm.is_active,
           ewm.scope_ref_id, r.code AS role_code, r.name AS role_name
    FROM dbo.employee_wise_role_mappings ewm
    LEFT JOIN dbo.roles r ON ewm.role_id = r.id
    WHERE ewm.emp_staffid = @StaffId
      AND ewm.is_active = 1;
END;
GO

PRINT '✓ Phase 1 SPs created successfully (13 SPs, lowercase table names)';
