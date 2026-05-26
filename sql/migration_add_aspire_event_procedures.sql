-- Migration: Add stored procedures for Aspire event sync reads

CREATE OR ALTER PROCEDURE dbo.usp_GetAspireExitEvents
    @since DATETIME2,
    @future DATETIME2
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        RTRIM(EmpId) AS EmpId,
        ResignationDate,
        LastWorkingDate,
        ExitType,
        ResignationReason,
        ResignedStatus,
        ResignationRevertDate,
        Project,
        Account
    FROM [DBO].[SEP_ResignationDetails]
    WHERE IsActive = 1
      AND IsDeleted = 0
      AND ResignationRevertDate IS NULL
      AND (
          (LastWorkingDate >= @since AND LastWorkingDate <= @future)
          OR (AddedOn >= @since)
          OR (ModifiedOn >= @since)
      );
END;
GO

CREATE OR ALTER PROCEDURE dbo.usp_GetAspireProjectReleaseEvents
    @since DATETIME2,
    @today DATETIME2
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
    WHERE IsActive = 1
      AND AllocationEndDate >= @since
      AND AllocationEndDate <= @today;
END;
GO

CREATE OR ALTER PROCEDURE dbo.usp_GetAspireReleaseReasons
AS
BEGIN
    SET NOCOUNT ON;

    SELECT Id, ReleaseReason
    FROM [DBO].[RPT_Release_Reason]
    WHERE IsActive = 1;
END;
GO

CREATE OR ALTER PROCEDURE dbo.usp_GetAspireBenchEvents
    @since DATETIME2,
    @today DATETIME2
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
    FROM [DBO].[RPT_PROJECT_ASSIGNMENT] pa
    JOIN [DBO].[ERM_EMPLOYEE_MASTER] e
        ON RTRIM(e.EMP_STAFFID) = RTRIM(pa.ASG_EMP_STAFFID)
    JOIN [DBO].[RPT_PROJECT_MASTER] p
        ON pa.ASG_PROJECT_ID = p.PROJECT_ID
    WHERE RTRIM(e.EMP_ISACTIVE) = '1'
      AND (p.PROJECT_NAME LIKE '%Corporate Pool%' OR p.PROJECT_NAME LIKE '%Corp Pool%')
      AND pa.ASG_TIMESTAMP >= @since
      AND (pa.PROJECT_ENDDATE IS NULL OR pa.PROJECT_ENDDATE >= @today);
END;
GO