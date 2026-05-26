"""
Phase 2 integration service for platform CRUD operations.

Uses stored procedures when Phase 2 is enabled and falls back to the existing
ORM implementation only when the feature flag is disabled. For write operations,
SP failures are raised instead of retried through ORM to avoid double mutations.
"""

import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.feature_flags import is_phase2_platform_enabled, log_sp_usage
from app.models.platform import Platform, PlatformContract
from app.schemas.platform import PlatformCreate
from app.services.phase2_sp_wrappers import (
    exec_usp_CreatePlatform,
    exec_usp_DeletePlatform,
    exec_usp_UpdatePlatform,
    Phase2SPError,
)

logger = logging.getLogger(__name__)


def _create_platform_orm(db: Session, payload: PlatformCreate) -> Platform:
    platform = Platform(
        name=payload.name,
        vendor=payload.vendor,
        category=payload.category,
        agreement_type=payload.agreement_type,
        license_type=payload.license_type,
        billing_period=payload.billing_period,
        currency=payload.currency,
        inactivity_days=payload.inactivity_days,
        contractor_allowed=payload.contractor_allowed,
        shared_allowed=payload.shared_allowed,
        api_available=payload.api_available,
        notes=payload.notes,
        effective_date=payload.effective_date,
        renewal_date=payload.renewal_date,
        is_active=True,
    )
    db.add(platform)
    db.flush()

    contract = PlatformContract(
        platform_id=platform.id,
        cost_model=payload.license_type,
        seat_cost=payload.seat_cost,
        enterprise_cost=payload.enterprise_cost,
        contracted_seats=payload.contracted_seats,
        allocation_method=payload.allocation_method,
        effective_from=payload.effective_date,
        effective_to=payload.renewal_date,
    )
    db.add(contract)
    db.commit()
    db.refresh(platform)
    return platform


def _update_platform_orm(db: Session, platform_id: int, payload: PlatformCreate) -> Platform:
    platform = db.get(Platform, platform_id)
    if not platform:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")

    platform.name = payload.name
    platform.vendor = payload.vendor
    platform.category = payload.category
    platform.agreement_type = payload.agreement_type
    platform.license_type = payload.license_type
    platform.billing_period = payload.billing_period
    platform.currency = payload.currency
    platform.inactivity_days = payload.inactivity_days
    platform.contractor_allowed = payload.contractor_allowed
    platform.shared_allowed = payload.shared_allowed
    platform.api_available = payload.api_available
    platform.notes = payload.notes
    platform.effective_date = payload.effective_date
    platform.renewal_date = payload.renewal_date

    db.add(platform)
    db.flush()

    contract = db.scalars(
        select(PlatformContract).where(PlatformContract.platform_id == platform_id)
    ).first()
    if contract:
        contract.cost_model = payload.license_type
        contract.seat_cost = payload.seat_cost
        contract.enterprise_cost = payload.enterprise_cost
        contract.contracted_seats = payload.contracted_seats
        contract.allocation_method = payload.allocation_method
        contract.effective_from = payload.effective_date
        contract.effective_to = payload.renewal_date
        db.add(contract)
    else:
        db.add(
            PlatformContract(
                platform_id=platform.id,
                cost_model=payload.license_type,
                seat_cost=payload.seat_cost,
                enterprise_cost=payload.enterprise_cost,
                contracted_seats=payload.contracted_seats,
                allocation_method=payload.allocation_method,
                effective_from=payload.effective_date,
                effective_to=payload.renewal_date,
            )
        )

    db.commit()
    db.refresh(platform)
    return platform


def _delete_platform_orm(db: Session, platform_id: int) -> None:
    platform = db.get(Platform, platform_id)
    if not platform:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")

    contracts = db.scalars(
        select(PlatformContract).where(PlatformContract.platform_id == platform_id)
    ).all()
    for contract in contracts:
        db.delete(contract)

    db.delete(platform)
    db.commit()


def create_platform_phase2(db: Session, payload: PlatformCreate) -> Platform:
    """Create platform using Phase 2 SP when enabled, ORM otherwise."""
    if is_phase2_platform_enabled():
        try:
            log_sp_usage("create_platform", True)
            platform_id = exec_usp_CreatePlatform(db, payload)
            db.commit()
            platform = db.get(Platform, platform_id) if platform_id else None
            if not platform:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Platform creation failed")
            return platform
        except HTTPException:
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Phase 2 SP failed for create platform")
            raise Phase2SPError("Phase 2 create platform failed") from exc

    log_sp_usage("create_platform", False)
    return _create_platform_orm(db, payload)


def update_platform_phase2(db: Session, platform_id: int, payload: PlatformCreate) -> Platform:
    """Update platform using Phase 2 SP when enabled, ORM otherwise."""
    if is_phase2_platform_enabled():
        try:
            log_sp_usage("update_platform", True)
            updated = exec_usp_UpdatePlatform(db, platform_id, payload)
            if not updated:
                db.rollback()
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")
            db.commit()
            platform = db.get(Platform, platform_id)
            if not platform:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")
            return platform
        except HTTPException:
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Phase 2 SP failed for update platform")
            raise Phase2SPError("Phase 2 update platform failed") from exc

    log_sp_usage("update_platform", False)
    return _update_platform_orm(db, platform_id, payload)


def delete_platform_phase2(db: Session, platform_id: int) -> None:
    """Delete platform using Phase 2 SP when enabled, ORM otherwise."""
    if is_phase2_platform_enabled():
        try:
            log_sp_usage("delete_platform", True)
            deleted = exec_usp_DeletePlatform(db, platform_id)
            if not deleted:
                db.rollback()
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")
            db.commit()
            return
        except HTTPException:
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Phase 2 SP failed for delete platform")
            raise Phase2SPError("Phase 2 delete platform failed") from exc

    log_sp_usage("delete_platform", False)
    _delete_platform_orm(db, platform_id)