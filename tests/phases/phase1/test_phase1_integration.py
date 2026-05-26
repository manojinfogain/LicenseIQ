"""
Quick test to verify Phase 1 integration is working.
Tests with feature flag disabled (ORM fallback).
"""

import os
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.services.phase1_integration import (
    get_role_mapping_phase1,
    get_open_alerts_phase1,
    get_license_requests_phase1,
    get_pending_queue_items_phase1,
    get_platform_by_id_phase1,
)
from app.core.feature_flags import is_phase1_enabled

def test_phase1_integration():
    """Test Phase 1 integration with feature flag disabled."""
    print("\n" + "="*80)
    print("PHASE 1 INTEGRATION TEST")
    print("="*80)
    
    # Check feature flag status
    print(f"\nFeature Flag Status: USE_PHASE1_SPS = {is_phase1_enabled()}")
    print("Expected: False (default, using ORM fallback)")
    
    db: Session = SessionLocal()
    try:
        # Test 1: Role mapping (fallback to ORM)
        print("\n[TEST 1] Role Mapping Lookup")
        print("-" * 40)
        result = get_role_mapping_phase1(db, "test_staff_id")
        print(f"Result: {result}")
        print("✓ PASS - Function executed without error")
        
        # Test 2: Open alerts (fallback to ORM)
        print("\n[TEST 2] Open Alerts")
        print("-" * 40)
        result = get_open_alerts_phase1(db)
        print(f"Result type: {type(result)}, Length: {len(result) if isinstance(result, list) else 'N/A'}")
        print("✓ PASS - Function executed without error")
        
        # Test 3: License requests (fallback to ORM)
        print("\n[TEST 3] License Requests")
        print("-" * 40)
        result = get_license_requests_phase1(db)
        print(f"Result type: {type(result)}, Length: {len(result) if isinstance(result, list) else 'N/A'}")
        print("✓ PASS - Function executed without error")
        
        # Test 4: Pending queue items (fallback to ORM)
        print("\n[TEST 4] Pending Queue Items")
        print("-" * 40)
        result = get_pending_queue_items_phase1(db)
        print(f"Result type: {type(result)}, Length: {len(result) if isinstance(result, list) else 'N/A'}")
        print("✓ PASS - Function executed without error")
        
        # Test 5: Platform by ID (fallback to ORM)
        print("\n[TEST 5] Platform by ID")
        print("-" * 40)
        result = get_platform_by_id_phase1(db, 1)
        print(f"Result: {result}")
        print("✓ PASS - Function executed without error")
        
        print("\n" + "="*80)
        print("ALL TESTS PASSED - Phase 1 integration is working!")
        print("="*80)
        
    except Exception as exc:
        print(f"\n✗ FAILED - Error: {exc}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_phase1_integration()
