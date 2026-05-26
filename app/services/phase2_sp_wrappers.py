"""
Phase 2 stored procedure wrappers for platform CRUD operations.
"""

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.platform import PlatformCreate


class Phase2SPError(Exception):
    """Raised when a Phase 2 stored procedure call fails."""


def exec_usp_CreatePlatform(db: Session, payload: PlatformCreate) -> Optional[int]:
    """Create a platform and its primary contract via stored procedure."""
    try:
        result = db.execute(
            text(
                """
                EXEC dbo.usp_CreatePlatform
                    @Name = :name,
                    @Vendor = :vendor,
                    @Category = :category,
                    @AgreementType = :agreement_type,
                    @LicenseType = :license_type,
                    @BillingPeriod = :billing_period,
                    @Currency = :currency,
                    @InactivityDays = :inactivity_days,
                    @ContractorAllowed = :contractor_allowed,
                    @SharedAllowed = :shared_allowed,
                    @ApiAvailable = :api_available,
                    @Notes = :notes,
                    @EffectiveDate = :effective_date,
                    @RenewalDate = :renewal_date,
                    @SeatCost = :seat_cost,
                    @EnterpriseCost = :enterprise_cost,
                    @ContractedSeats = :contracted_seats,
                    @AllocationMethod = :allocation_method
                """
            ),
            payload.model_dump(),
        ).fetchone()
        return int(result[0]) if result else None
    except Exception as exc:
        raise Phase2SPError(f"usp_CreatePlatform failed: {exc}") from exc


def exec_usp_UpdatePlatform(db: Session, platform_id: int, payload: PlatformCreate) -> bool:
    """Update a platform and its primary contract via stored procedure."""
    try:
        params = {"platform_id": platform_id, **payload.model_dump()}
        result = db.execute(
            text(
                """
                EXEC dbo.usp_UpdatePlatform
                    @PlatformId = :platform_id,
                    @Name = :name,
                    @Vendor = :vendor,
                    @Category = :category,
                    @AgreementType = :agreement_type,
                    @LicenseType = :license_type,
                    @BillingPeriod = :billing_period,
                    @Currency = :currency,
                    @InactivityDays = :inactivity_days,
                    @ContractorAllowed = :contractor_allowed,
                    @SharedAllowed = :shared_allowed,
                    @ApiAvailable = :api_available,
                    @Notes = :notes,
                    @EffectiveDate = :effective_date,
                    @RenewalDate = :renewal_date,
                    @SeatCost = :seat_cost,
                    @EnterpriseCost = :enterprise_cost,
                    @ContractedSeats = :contracted_seats,
                    @AllocationMethod = :allocation_method
                """
            ),
            params,
        ).fetchone()
        return bool(result and result[0])
    except Exception as exc:
        raise Phase2SPError(f"usp_UpdatePlatform failed: {exc}") from exc


def exec_usp_DeletePlatform(db: Session, platform_id: int) -> bool:
    """Delete a platform and related contracts via stored procedure."""
    try:
        result = db.execute(
            text(
                """
                EXEC dbo.usp_DeletePlatform
                    @PlatformId = :platform_id
                """
            ),
            {"platform_id": platform_id},
        ).fetchone()
        return bool(result and result[0])
    except Exception as exc:
        raise Phase2SPError(f"usp_DeletePlatform failed: {exc}") from exc