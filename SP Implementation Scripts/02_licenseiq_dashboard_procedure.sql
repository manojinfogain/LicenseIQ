-- =============================================================================
-- FILE    : 02_licenseiq_dashboard_procedure.sql
-- TARGET  : LicenseIQ application database (IGDNIWVDE01\MSSQLSERVER2019)
-- PURPOSE : Create / update the stored procedure used by LicenseIQ to aggregate
--           dashboard summary metrics (total / active / flagged licenses, spend,
--           open alerts) for a given set of employees.
-- HOW     : Run this entire script in SSMS against the LicenseIQ application DB.
--           Uses CREATE OR ALTER — safe to re-run.
-- =============================================================================

USE [<LicenseIQDatabase>];   -- ← replace <LicenseIQDatabase> with actual DB name
GO

-- ---------------------------------------------------------------------------
-- usp_GetDashboardSummaryMetrics
--    Aggregates license and alert counts for the supplied comma-separated list
--    of employee IDs. Called by the /api/v1/dashboard endpoint.
--
--    Parameters:
--      @employee_ids  NVARCHAR(MAX)  — comma-separated integer employee IDs
--                                      e.g. '1001,1002,1003'
-- ---------------------------------------------------------------------------
CREATE OR ALTER PROCEDURE dbo.usp_GetDashboardSummaryMetrics
    @employee_ids NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;

    WITH employee_ids AS (
        -- Parse the comma-separated list into a set of integer IDs
        SELECT DISTINCT TRY_CAST(LTRIM(RTRIM(value)) AS INT) AS employee_id
        FROM   STRING_SPLIT(@employee_ids, ',')
        WHERE  TRY_CAST(LTRIM(RTRIM(value)) AS INT) IS NOT NULL
    )
    SELECT
        COUNT(CASE WHEN la.revoked_date IS NULL                                    THEN 1 END) AS total_licenses,
        COUNT(CASE WHEN la.revoked_date IS NULL AND la.status = 'active'           THEN 1 END) AS active_licenses,
        COUNT(CASE WHEN la.revoked_date IS NULL AND la.status <> 'active'          THEN 1 END) AS flagged_licenses,
        COALESCE(SUM(CASE WHEN la.revoked_date IS NULL THEN la.monthly_cost ELSE 0 END), 0)    AS monthly_spend,
        (
            SELECT COUNT(*)
            FROM   alerts        a
            JOIN   employee_ids  eid ON eid.employee_id = a.employee_id
            WHERE  a.status = 'open'
        ) AS open_alerts
    FROM  license_allocations la
    JOIN  employee_ids eid ON eid.employee_id = la.employee_id;
END;
GO

-- =============================================================================
-- VERIFICATION — run after creation
-- =============================================================================
SELECT name, create_date, modify_date
FROM   sys.procedures
WHERE  name = 'usp_GetDashboardSummaryMetrics';
GO

-- Smoke-test (replace IDs with real employee IDs from your data)
EXEC dbo.usp_GetDashboardSummaryMetrics @employee_ids = '1,2,3';
GO
