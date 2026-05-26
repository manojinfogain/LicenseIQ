-- =============================================================================
-- FILE    : 01_aspire_event_procedures.sql
-- TARGET  : Aspire source database (read-only Aspire DB on IGDNIWVDE01\MSSQLSERVER2019)
-- PURPOSE : Create / update the 4 stored procedures used by LicenseIQ to detect
--           employee status-change events (exit, project release, bench placement).
-- HOW     : Run this entire script in SSMS against the Aspire database.
--           All statements use CREATE OR ALTER, so they are safe to re-run.
-- =============================================================================

USE [<AspireDatabase>];   -- ← replace <AspireDatabase> with the actual DB name
GO

-- ---------------------------------------------------------------------------
-- 1. usp_GetAspireExitEvents
--    Returns employees who have a resignation record with an active last-working
--    date that falls within the supplied window (@since → @future).
--    Called by LicenseIQ aspire-sync to raise EXIT smart-alerts.
-- ---------------------------------------------------------------------------
CREATE OR ALTER PROCEDURE dbo.usp_GetAspireExitEvents
    @since  DATETIME2,   -- look-back start  (typically NOW - 30 days)
    @future DATETIME2    -- look-forward end (typically NOW + 15 days)
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        RTRIM(EmpId)             AS EmpId,
        ResignationDate,
        LastWorkingDate,
        ExitType,
        ResignationReason,
        ResignedStatus,
        ResignationRevertDate,
        Project,
        Account
    FROM [DBO].[SEP_ResignationDetails]
    WHERE IsActive              = 1
      AND IsDeleted             = 0
      AND ResignationRevertDate IS NULL
      AND (
              (LastWorkingDate >= @since AND LastWorkingDate <= @future)
           OR  AddedOn          >= @since
           OR  ModifiedOn       >= @since
          );
END;
GO

-- ---------------------------------------------------------------------------
-- 2. usp_GetAspireProjectReleaseEvents
--    Returns employees released from a project within the look-back window.
--    Called by LicenseIQ aspire-sync to raise PROJECT_CHANGE smart-alerts.
-- ---------------------------------------------------------------------------
CREATE OR ALTER PROCEDURE dbo.usp_GetAspireProjectReleaseEvents
    @since DATETIME2,   -- look-back start
    @today DATETIME2    -- current date / upper bound
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        RTRIM(EmployeeId) AS EmployeeId,
        AccountId,
        ProjectId,
        ReleaseReason,
        AllocationEndDate,
        FeedbackGivenOn
    FROM [DBO].[RPT_FeedbackOnRelease]
    WHERE IsActive        = 1
      AND AllocationEndDate >= @since
      AND AllocationEndDate <= @today;
END;
GO

-- ---------------------------------------------------------------------------
-- 3. usp_GetAspireReleaseReasons
--    Returns the lookup table of release-reason codes and descriptions.
--    Called once per aspire-sync cycle to resolve reason codes into text.
-- ---------------------------------------------------------------------------
CREATE OR ALTER PROCEDURE dbo.usp_GetAspireReleaseReasons
AS
BEGIN
    SET NOCOUNT ON;

    SELECT Id, ReleaseReason
    FROM [DBO].[RPT_Release_Reason]
    WHERE IsActive = 1;
END;
GO

-- ---------------------------------------------------------------------------
-- 4. usp_GetAspireBenchEvents
--    Returns employees currently or recently placed in a Corporate-Pool project
--    (bench placement). Called by LicenseIQ aspire-sync to raise BENCH smart-alerts.
-- ---------------------------------------------------------------------------
CREATE OR ALTER PROCEDURE dbo.usp_GetAspireBenchEvents
    @since DATETIME2,   -- look-back start
    @today DATETIME2    -- current date / upper bound
AS
BEGIN
    SET NOCOUNT ON;

    SELECT DISTINCT
        RTRIM(pa.ASG_EMP_STAFFID) AS EmpId,
        p.PROJECT_NAME,
        pa.BILLABLE,
        pa.PROJECT_STARTDATE,
        pa.PROJECT_ENDDATE,
        pa.ASG_TIMESTAMP
    FROM [DBO].[RPT_PROJECT_ASSIGNMENT]  pa
    JOIN [DBO].[ERM_EMPLOYEE_MASTER]     e
        ON  RTRIM(e.EMP_STAFFID) = RTRIM(pa.ASG_EMP_STAFFID)
    JOIN [DBO].[RPT_PROJECT_MASTER]      p
        ON  pa.ASG_PROJECT_ID    = p.PROJECT_ID
    WHERE RTRIM(e.EMP_ISACTIVE) = '1'
      AND (
              p.PROJECT_NAME LIKE '%Corporate Pool%'
           OR p.PROJECT_NAME LIKE '%Corp Pool%'
          )
      AND pa.ASG_TIMESTAMP >= @since
      AND (pa.PROJECT_ENDDATE IS NULL OR pa.PROJECT_ENDDATE >= @today);
END;
GO

-- =============================================================================
-- VERIFICATION — run after creation to confirm all 4 procedures exist
-- =============================================================================
SELECT name, create_date, modify_date
FROM   sys.procedures
WHERE  name IN (
    'usp_GetAspireExitEvents',
    'usp_GetAspireProjectReleaseEvents',
    'usp_GetAspireReleaseReasons',
    'usp_GetAspireBenchEvents'
)
ORDER BY name;
GO

-- Quick smoke-test (adjust date range as needed)
DECLARE @since  DATETIME2 = DATEADD(DAY, -30, SYSDATETIME());
DECLARE @future DATETIME2 = DATEADD(DAY, +15, SYSDATETIME());
DECLARE @today  DATETIME2 = SYSDATETIME();

EXEC dbo.usp_GetAspireExitEvents            @since = @since, @future = @future;
EXEC dbo.usp_GetAspireProjectReleaseEvents  @since = @since, @today  = @today;
EXEC dbo.usp_GetAspireReleaseReasons;
EXEC dbo.usp_GetAspireBenchEvents           @since = @since, @today  = @today;
GO
