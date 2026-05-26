-- Login accounts: hashed passwords only (no plaintext in application code).
IF OBJECT_ID(N'dbo.login_accounts', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.login_accounts (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        email NVARCHAR(255) NOT NULL,
        password_hash NVARCHAR(512) NOT NULL,
        role_code NVARCHAR(50) NOT NULL,
        role_display_name NVARCHAR(100) NOT NULL,
        is_active BIT NOT NULL CONSTRAINT DF_login_accounts_is_active DEFAULT (1),
        created_at DATETIME2 NOT NULL CONSTRAINT DF_login_accounts_created_at DEFAULT (SYSUTCDATETIME()),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_login_accounts_updated_at DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT UQ_login_accounts_email UNIQUE (email)
    );

    CREATE INDEX IX_login_accounts_role_code ON dbo.login_accounts (role_code);
    CREATE INDEX IX_login_accounts_is_active ON dbo.login_accounts (is_active);
END
GO

;WITH src AS (
    SELECT *
    FROM (VALUES
        (N'ramesh.krishnan@tenarai.com', N'e55d8ecbbd9a951270a505f3f0fc050d$a5dad9a3d6ee0cbc7ecddfca2e6fed922774023390140cb5cdac864477d79da2', N'gdl', N'GDL'),
        (N'dharampal.singh@tenarai.com', N'8a1192222a88c7fa076ed7da6476a2d2$716211564c4983e6336d3234f5539b607f585849224d0ae1e1600cba599201f6', N'pm', N'Project Manager'),
        (N'rahul.chandan@tenarai.com', N'dbd014a6d478c0b1917d98a40a3f7603$3165a195d2c798b48044dbeeb1045d3d708e1c1a996cb39f224ea51fee1becbb', N'admin', N'IT Admin'),
        (N'shailanderk@tenarai.com', N'8493396e40abb3ff54cff22df7f255cf$ed913406d6227ee57616bd24c54536f157106545d6584d6c1c18dcfa4c09b704', N'account', N'Account Owner'),
        (N'kulesh.bansal@tenarai.com', N'b77c24b557245b5af1a8f94c0d21fe21$54bb948a661fdbf523f806c0a4ee7c9d561fc1af2536cd025cf6afa5b6433aac', N'finance', N'Finance/CFO')
    ) AS v(email, password_hash, role_code, role_display_name)
)
MERGE dbo.login_accounts AS tgt
USING src
    ON LOWER(tgt.email) = LOWER(src.email)
WHEN MATCHED THEN
    UPDATE SET
        password_hash = src.password_hash,
        role_code = src.role_code,
        role_display_name = src.role_display_name,
        is_active = 1,
        updated_at = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (email, password_hash, role_code, role_display_name, is_active)
    VALUES (src.email, src.password_hash, src.role_code, src.role_display_name, 1);
GO
