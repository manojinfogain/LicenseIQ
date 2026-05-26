-- Migration: Add stored procedure for dashboard summary aggregates

CREATE OR ALTER PROCEDURE dbo.usp_GetDashboardSummaryMetrics
    @employee_ids NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;

    WITH employee_ids AS (
        SELECT DISTINCT TRY_CAST(LTRIM(RTRIM(value)) AS INT) AS employee_id
        FROM STRING_SPLIT(@employee_ids, ',')
        WHERE TRY_CAST(LTRIM(RTRIM(value)) AS INT) IS NOT NULL
    )
    SELECT
        COUNT(CASE WHEN la.revoked_date IS NULL THEN 1 END) AS total_licenses,
        COUNT(CASE WHEN la.revoked_date IS NULL AND la.status = 'active' THEN 1 END) AS active_licenses,
        COUNT(CASE WHEN la.revoked_date IS NULL AND la.status <> 'active' THEN 1 END) AS flagged_licenses,
        COALESCE(SUM(CASE WHEN la.revoked_date IS NULL THEN la.monthly_cost ELSE 0 END), 0) AS monthly_spend,
        (
            SELECT COUNT(*)
            FROM alerts a
            JOIN employee_ids eid ON eid.employee_id = a.employee_id
            WHERE a.status = 'open'
        ) AS open_alerts
    FROM license_allocations la
    JOIN employee_ids eid ON eid.employee_id = la.employee_id;
END;
GO