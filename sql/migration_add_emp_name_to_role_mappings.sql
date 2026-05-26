-- Migration: Add emp_name column to employee_wise_role_mappings
-- Run this once against the LicenseIQ application database.

IF NOT EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'employee_wise_role_mappings'
      AND COLUMN_NAME = 'emp_name'
)
BEGIN
    ALTER TABLE dbo.employee_wise_role_mappings
        ADD emp_name NVARCHAR(150) NULL;
END
GO
