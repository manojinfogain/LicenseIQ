/*
===============================================================================
Phase 2 Stored Procedures: Platform CRUD
===============================================================================
Uses the current application behavior as the source of truth:
- create platform + primary contract
- update platform + contract
- hard delete platform + contracts
*/

CREATE OR ALTER PROCEDURE dbo.usp_CreatePlatform
    @Name NVARCHAR(150),
    @Vendor NVARCHAR(150),
    @Category NVARCHAR(100),
    @AgreementType NVARCHAR(50),
    @LicenseType NVARCHAR(50),
    @BillingPeriod NVARCHAR(30),
    @Currency NVARCHAR(10) = 'USD',
    @InactivityDays INT = 30,
    @ContractorAllowed BIT = 1,
    @SharedAllowed BIT = 0,
    @ApiAvailable BIT = 0,
    @Notes NVARCHAR(500) = NULL,
    @EffectiveDate DATE = NULL,
    @RenewalDate DATE = NULL,
    @SeatCost DECIMAL(12, 2) = NULL,
    @EnterpriseCost DECIMAL(12, 2) = NULL,
    @ContractedSeats INT = NULL,
    @AllocationMethod NVARCHAR(50) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    BEGIN TRANSACTION;

    BEGIN TRY
        INSERT INTO dbo.platforms (
            name,
            vendor,
            category,
            agreement_type,
            license_type,
            billing_period,
            currency,
            inactivity_days,
            contractor_allowed,
            shared_allowed,
            api_available,
            notes,
            effective_date,
            renewal_date,
            is_active,
            created_at
        )
        VALUES (
            @Name,
            @Vendor,
            @Category,
            @AgreementType,
            @LicenseType,
            @BillingPeriod,
            @Currency,
            @InactivityDays,
            @ContractorAllowed,
            @SharedAllowed,
            @ApiAvailable,
            @Notes,
            @EffectiveDate,
            @RenewalDate,
            1,
            GETUTCDATE()
        );

        DECLARE @PlatformId INT = CAST(SCOPE_IDENTITY() AS INT);

        INSERT INTO dbo.platform_contracts (
            platform_id,
            cost_model,
            seat_cost,
            enterprise_cost,
            contracted_seats,
            allocation_method,
            effective_from,
            effective_to
        )
        VALUES (
            @PlatformId,
            @LicenseType,
            @SeatCost,
            @EnterpriseCost,
            @ContractedSeats,
            @AllocationMethod,
            @EffectiveDate,
            @RenewalDate
        );

        COMMIT TRANSACTION;
        SELECT @PlatformId AS platform_id;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO

CREATE OR ALTER PROCEDURE dbo.usp_UpdatePlatform
    @PlatformId INT,
    @Name NVARCHAR(150),
    @Vendor NVARCHAR(150),
    @Category NVARCHAR(100),
    @AgreementType NVARCHAR(50),
    @LicenseType NVARCHAR(50),
    @BillingPeriod NVARCHAR(30),
    @Currency NVARCHAR(10),
    @InactivityDays INT,
    @ContractorAllowed BIT,
    @SharedAllowed BIT,
    @ApiAvailable BIT,
    @Notes NVARCHAR(500) = NULL,
    @EffectiveDate DATE = NULL,
    @RenewalDate DATE = NULL,
    @SeatCost DECIMAL(12, 2) = NULL,
    @EnterpriseCost DECIMAL(12, 2) = NULL,
    @ContractedSeats INT = NULL,
    @AllocationMethod NVARCHAR(50) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    BEGIN TRANSACTION;

    BEGIN TRY
        UPDATE dbo.platforms
        SET
            name = @Name,
            vendor = @Vendor,
            category = @Category,
            agreement_type = @AgreementType,
            license_type = @LicenseType,
            billing_period = @BillingPeriod,
            currency = @Currency,
            inactivity_days = @InactivityDays,
            contractor_allowed = @ContractorAllowed,
            shared_allowed = @SharedAllowed,
            api_available = @ApiAvailable,
            notes = @Notes,
            effective_date = @EffectiveDate,
            renewal_date = @RenewalDate
        WHERE id = @PlatformId;

        IF @@ROWCOUNT = 0
        BEGIN
            ROLLBACK TRANSACTION;
            SELECT CAST(0 AS BIT) AS updated;
            RETURN;
        END

        IF EXISTS (SELECT 1 FROM dbo.platform_contracts WHERE platform_id = @PlatformId)
        BEGIN
            UPDATE dbo.platform_contracts
            SET
                cost_model = @LicenseType,
                seat_cost = @SeatCost,
                enterprise_cost = @EnterpriseCost,
                contracted_seats = @ContractedSeats,
                allocation_method = @AllocationMethod,
                effective_from = @EffectiveDate,
                effective_to = @RenewalDate
            WHERE platform_id = @PlatformId;
        END
        ELSE
        BEGIN
            INSERT INTO dbo.platform_contracts (
                platform_id,
                cost_model,
                seat_cost,
                enterprise_cost,
                contracted_seats,
                allocation_method,
                effective_from,
                effective_to
            )
            VALUES (
                @PlatformId,
                @LicenseType,
                @SeatCost,
                @EnterpriseCost,
                @ContractedSeats,
                @AllocationMethod,
                @EffectiveDate,
                @RenewalDate
            );
        END

        COMMIT TRANSACTION;
        SELECT CAST(1 AS BIT) AS updated;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO

CREATE OR ALTER PROCEDURE dbo.usp_DeletePlatform
    @PlatformId INT
AS
BEGIN
    SET NOCOUNT ON;

    BEGIN TRANSACTION;

    BEGIN TRY
        IF NOT EXISTS (SELECT 1 FROM dbo.platforms WHERE id = @PlatformId)
        BEGIN
            ROLLBACK TRANSACTION;
            SELECT CAST(0 AS BIT) AS deleted;
            RETURN;
        END

        DELETE FROM dbo.platform_contracts WHERE platform_id = @PlatformId;
        DELETE FROM dbo.platforms WHERE id = @PlatformId;

        COMMIT TRANSACTION;
        SELECT CAST(1 AS BIT) AS deleted;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO