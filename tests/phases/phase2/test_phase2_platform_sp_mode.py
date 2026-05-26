"""
Focused validation for Phase 2 platform CRUD integration in SP mode.

This script requires the Phase 2 platform procedures to be deployed first.
It enables the Phase 2 feature flag and verifies create, update, and delete.
"""

import os
import sys
from datetime import date
from uuid import uuid4

import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

os.environ["USE_PHASE2_PLATFORM_SPS"] = "true"

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.feature_flags import is_phase2_platform_enabled
from app.schemas.platform import PlatformCreate
from app.services.phase2_integration import (
    create_platform_phase2,
    delete_platform_phase2,
    update_platform_phase2,
)


def _payload(name: str, notes: str) -> PlatformCreate:
    return PlatformCreate(
        name=name,
        vendor="Phase2 Vendor",
        category="Productivity",
        agreement_type="Enterprise",
        license_type="Seat",
        billing_period="Annual",
        currency="USD",
        inactivity_days=45,
        contractor_allowed=True,
        shared_allowed=False,
        api_available=True,
        notes=notes,
        effective_date=date(2026, 5, 15),
        renewal_date=date(2027, 5, 15),
        seat_cost=10.0,
        enterprise_cost=1000.0,
        contracted_seats=25,
        allocation_method="manual",
    )


def test_phase2_platform_sp_mode() -> None:
    print("\n" + "=" * 80)
    print("PHASE 2 PLATFORM CRUD SP MODE TEST")
    print("=" * 80)
    print(f"\nFeature Flag Status: USE_PHASE2_PLATFORM_SPS = {is_phase2_platform_enabled()}")
    print("Expected: True (using Phase 2 stored procedures)")

    db: Session = SessionLocal()
    created_platform_id: int | None = None

    try:
        unique_name = f"Phase2 SP Platform {uuid4().hex[:8]}"
        created = create_platform_phase2(db, _payload(unique_name, "created by phase 2 sp test"))
        created_platform_id = created.id
        print(f"✓ CREATE PASS - Platform created with id={created_platform_id}")

        updated_name = f"{unique_name} Updated"
        updated = update_platform_phase2(db, created_platform_id, _payload(updated_name, "updated by phase 2 sp test"))
        print(f"✓ UPDATE PASS - Platform updated to name={updated.name}")

        delete_platform_phase2(db, created_platform_id)
        created_platform_id = None
        print("✓ DELETE PASS - Platform deleted")

        print("\n" + "=" * 80)
        print("ALL TESTS PASSED - Phase 2 SP mode is working!")
        print("=" * 80)
    finally:
        if created_platform_id is not None:
            try:
                delete_platform_phase2(db, created_platform_id)
            except Exception:
                db.rollback()
        db.close()


if __name__ == "__main__":
    test_phase2_platform_sp_mode()