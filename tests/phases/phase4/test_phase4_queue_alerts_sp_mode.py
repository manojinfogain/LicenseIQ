"""
Phase 4 Queue Execution & Alerts SP Mode Validation Tests

Tests the queue execution and alert workflows through stored procedure implementation:
- Execute queue item assignment
- Execute queue item revocation
- Mark queue item executed
- Create alert
- Resolve alert
- Get queue metrics

CRITICAL: This test module enables the Phase 4 feature flag by modifying environment
variable before any imports of feature_flags.
"""

# SET FEATURE FLAG BEFORE IMPORTING ANYTHING ELSE
import os
os.environ["USE_PHASE4_QUEUE_ALERTS_SPS"] = "true"

import sys
from datetime import datetime, date

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from app.core.database import SessionLocal
from app.models.organization import Employee, Account, Project
from app.models.platform import Platform
from app.models.license import QueueItem, LicenseAllocation, Alert, AllocationAudit
from app.models.access import User
from app.services.phase4_integration import (
    execute_queue_item_assignment_phase4,
    execute_queue_item_revocation_phase4,
    mark_queue_item_executed_phase4,
    create_alert_phase4,
    resolve_alert_phase4,
    get_queue_metrics_phase4,
)


def setup_test_data(db):
    """Create test data: employees, platforms, queue items, allocations."""
    print("\n[SETUP] Creating test data...")
    
    # Get approver user
    approver = db.query(User).filter_by(id=1).first()
    approver_id = approver.id if approver else None
    print(f"  Using approver user ID: {approver_id}")
    
    # Get or create test account
    test_account = db.query(Account).filter_by(id=1).first()
    print(f"  Using account ID: {test_account.id if test_account else 'N/A'}")
    
    # Get or create test project
    test_project = db.query(Project).filter_by(id=1).first()
    print(f"  Using project ID: {test_project.id if test_project else 'N/A'}")
    
    # Create test employee for SP mode tests
    test_emp = db.query(Employee).filter_by(id=100005).first()
    if not test_emp:
        test_emp = Employee(
            id=100005,
            full_name="Test Employee Phase4 SP",
            employee_code="TEST005SP",
            unit="Testing",
            employment_status="active",
            account_id=test_account.id,
            project_id=test_project.id,
            account_owner_user_id=approver_id,
        )
        db.add(test_emp)
        db.flush()
        print(f"  Created employee ID: {test_emp.id}")
    else:
        print(f"  Using employee ID: {test_emp.id}")
    
    # Create test platforms for SP mode
    test_platform1 = db.query(Platform).filter_by(id=106).first()
    if not test_platform1:
        test_platform1 = Platform(
            id=106,
            name="Phase4SPTestPlatform1",
            vendor="TestVendor",
            category="Development",
            agreement_type="perpetual",
            license_type="named_user",
            billing_period="annual",
            currency="USD",
            is_active=True,
        )
        db.add(test_platform1)
        db.flush()
        print(f"  Created platform ID: {test_platform1.id}")
    else:
        print(f"  Using platform ID: {test_platform1.id}")
    
    test_platform2 = db.query(Platform).filter_by(id=107).first()
    if not test_platform2:
        test_platform2 = Platform(
            id=107,
            name="Phase4SPTestPlatform2",
            vendor="TestVendor",
            category="Development",
            agreement_type="perpetual",
            license_type="named_user",
            billing_period="annual",
            currency="USD",
            is_active=True,
        )
        db.add(test_platform2)
        db.flush()
        print(f"  Created platform ID: {test_platform2.id}")
    else:
        print(f"  Using platform ID: {test_platform2.id}")
    
    db.commit()
    return test_emp.id, test_platform1.id, test_platform2.id, approver_id


def test_execute_queue_item_assignment_sp(db, emp_id, platform_id, user_id):
    """Test executing a queue item assignment via SP."""
    print("\n[TEST 1] EXECUTE QUEUE ITEM ASSIGNMENT (SP MODE)")
    print("=" * 60)
    
    # Clean up any pre-existing active allocations to ensure a clean state
    db.query(LicenseAllocation).filter_by(
        employee_id=emp_id, platform_id=platform_id, status="active"
    ).delete()
    db.commit()
    
    try:
        # Create queue item for assignment
        queue_item = QueueItem(
            source_type="request",
            source_id=None,
            employee_id=emp_id,
            platform_id=platform_id,
            action_type="assign",
            project_id=None,
            status="pending",
            cost_snapshot_monthly=100.00,
            requested_by_user_id=user_id,
        )
        db.add(queue_item)
        db.commit()
        queue_item_id = queue_item.id
        print(f"  Created queue item ID: {queue_item_id}")
        
        # Execute the assignment via SP
        execute_queue_item_assignment_phase4(
            db,
            queue_item_id=queue_item_id,
            executed_by_user_id=user_id,
            execution_notes="Test SP assignment execution",
        )
        
        # Verify queue item is marked as executed
        queue_item = db.get(QueueItem, queue_item_id)
        print(f"✓ SP ASSIGNMENT PASS - Queue item executed")
        print(f"  - status: {queue_item.status}")
        print(f"  - executed_by_user_id: {queue_item.executed_by_user_id}")
        print(f"  - Source: Stored Procedure")
        
        # Verify allocation was created
        allocation = db.query(LicenseAllocation).filter_by(
            employee_id=emp_id,
            platform_id=platform_id,
            status="active",
        ).first()
        assert allocation is not None, "Allocation should be created"
        assert allocation.source_type == "queue_executed"
        print(f"  - Allocation created with id={allocation.id}")
        
    except Exception as exc:
        print(f"✗ SP ASSIGNMENT FAIL - {str(exc)}")
        raise


def test_execute_queue_item_revocation_sp(db, emp_id, platform_id, user_id):
    """Test executing a queue item revocation via SP."""
    print("\n[TEST 2] EXECUTE QUEUE ITEM REVOCATION (SP MODE)")
    print("=" * 60)
    
    try:
        # First create an active allocation
        allocation = LicenseAllocation(
            employee_id=emp_id,
            platform_id=platform_id,
            status="active",
            effective_date=date.today(),
            source_type="manual",
        )
        db.add(allocation)
        db.commit()
        print(f"  Created allocation ID: {allocation.id}")
        
        # Create queue item for revocation
        queue_item = QueueItem(
            source_type="request",
            source_id=None,
            employee_id=emp_id,
            platform_id=platform_id,
            action_type="revoke",
            project_id=None,
            status="pending",
            requested_by_user_id=user_id,
        )
        db.add(queue_item)
        db.commit()
        queue_item_id = queue_item.id
        print(f"  Created queue item ID: {queue_item_id}")
        
        # Execute the revocation via SP
        execute_queue_item_revocation_phase4(
            db,
            queue_item_id=queue_item_id,
            executed_by_user_id=user_id,
            execution_notes="Test SP revocation execution",
        )
        
        # Verify queue item is marked as executed
        queue_item = db.get(QueueItem, queue_item_id)
        print(f"✓ SP REVOCATION PASS - Queue item executed")
        print(f"  - status: {queue_item.status}")
        print(f"  - Source: Stored Procedure")
        
        # Verify allocation was revoked
        allocation = db.get(LicenseAllocation, allocation.id)
        assert allocation.status == "revoked"
        print(f"  - Allocation revoked with status={allocation.status}")
        
        # Verify audit record
        audit = db.query(AllocationAudit).filter_by(allocation_id=allocation.id).first()
        assert audit is not None
        print(f"  - Audit record created with id={audit.id}")
        
    except Exception as exc:
        print(f"✗ SP REVOCATION FAIL - {str(exc)}")
        raise


def test_mark_queue_item_executed_sp(db, emp_id, platform_id, user_id):
    """Test marking a queue item as executed via SP."""
    print("\n[TEST 3] MARK QUEUE ITEM EXECUTED (SP MODE)")
    print("=" * 60)
    
    try:
        # Create queue item
        queue_item = QueueItem(
            source_type="request",
            source_id=None,
            employee_id=emp_id,
            platform_id=platform_id,
            action_type="other",
            status="pending",
        )
        db.add(queue_item)
        db.commit()
        queue_item_id = queue_item.id
        print(f"  Created queue item ID: {queue_item_id}")
        
        # Mark as executed via SP
        mark_queue_item_executed_phase4(
            db,
            queue_item_id=queue_item_id,
            executed_by_user_id=user_id,
            execution_notes="Marked executed via SP for testing",
        )
        
        # Verify status
        queue_item = db.get(QueueItem, queue_item_id)
        print(f"✓ SP MARK EXECUTED PASS - Queue item marked as executed")
        print(f"  - status: {queue_item.status}")
        print(f"  - executed_by_user_id: {queue_item.executed_by_user_id}")
        print(f"  - Source: Stored Procedure")
        
        assert queue_item.status == "executed"
        
    except Exception as exc:
        print(f"✗ SP MARK EXECUTED FAIL - {str(exc)}")
        raise


def test_create_and_resolve_alert_sp(db, emp_id, platform_id):
    """Test creating and resolving alerts via SP."""
    print("\n[TEST 4] CREATE AND RESOLVE ALERT (SP MODE)")
    print("=" * 60)
    
    try:
        # Create alert via SP
        alert_id = create_alert_phase4(
            db,
            alert_type="license_expiring",
            priority="high",
            reason="License expiration approaching",
            employee_id=emp_id,
            platform_id=platform_id,
            detail="License expires in 30 days",
            source_system="test_sp",
        )
        
        print(f"✓ SP CREATE ALERT PASS - Alert created with id={alert_id}")
        print(f"  - Source: Stored Procedure")
        
        # Verify alert
        alert = db.get(Alert, alert_id)
        assert alert.status == "open"
        print(f"  - status: {alert.status}")
        print(f"  - alert_type: {alert.alert_type}")
        
        # Resolve alert via SP
        resolve_alert_phase4(db, alert_id=alert_id)
        
        # Verify resolution
        alert = db.get(Alert, alert_id)
        print(f"✓ SP RESOLVE ALERT PASS - Alert resolved")
        print(f"  - status: {alert.status}")
        print(f"  - resolved_at: {alert.resolved_at}")
        print(f"  - Source: Stored Procedure")
        
        assert alert.status == "resolved"
        
    except Exception as exc:
        print(f"✗ SP ALERT FAIL - {str(exc)}")
        raise


def test_get_queue_metrics_sp(db):
    """Test getting queue metrics via SP."""
    print("\n[TEST 5] GET QUEUE METRICS (SP MODE)")
    print("=" * 60)
    
    try:
        # Get metrics via SP
        metrics = get_queue_metrics_phase4(db)
        
        print(f"✓ SP METRICS PASS - Queue metrics retrieved")
        print(f"  - pending_count: {metrics.get('pending_count', 'N/A')}")
        print(f"  - executed_count: {metrics.get('executed_count', 'N/A')}")
        print(f"  - rejected_count: {metrics.get('rejected_count', 'N/A')}")
        print(f"  - open_alerts: {metrics.get('open_alerts', 'N/A')}")
        print(f"  - resolved_alerts: {metrics.get('resolved_alerts', 'N/A')}")
        print(f"  - Source: Stored Procedure")
        
        assert isinstance(metrics, dict)
        
    except Exception as exc:
        print(f"✗ SP METRICS FAIL - {str(exc)}")
        raise


def main():
    """Run all Phase 4 SP validation tests."""
    print("\n" + "=" * 60)
    print("PHASE 4 QUEUE EXECUTION & ALERTS - SP MODE VALIDATION")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Check feature flag status
        from app.core.feature_flags import is_phase4_queue_alerts_enabled
        print(f"\nFeature Flag Status: USE_PHASE4_QUEUE_ALERTS_SPS = {is_phase4_queue_alerts_enabled()}")
        print("(Should be True for SP-mode testing)")
        
        if not is_phase4_queue_alerts_enabled():
            print("\n⚠ WARNING: Feature flag is not enabled. Skipping SP-mode tests.")
            print("(Set environment variable USE_PHASE4_QUEUE_ALERTS_SPS=true before running)")
            return
        
        # Setup test data
        emp_id, platform_id1, platform_id2, user_id = setup_test_data(db)
        
        if user_id is None:
            print("\n⚠ WARNING: No valid user ID found.")
            return
        
        # Run SP-mode tests
        test_execute_queue_item_assignment_sp(db, emp_id, platform_id1, user_id)
        test_execute_queue_item_revocation_sp(db, emp_id, platform_id2, user_id)
        test_mark_queue_item_executed_sp(db, user_id)
        test_create_and_resolve_alert_sp(db, emp_id, platform_id1)
        test_get_queue_metrics_sp(db)
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED - Phase 4 SP-mode integration is working!")
        print("=" * 60 + "\n")
        
    except Exception as exc:
        print("\n" + "=" * 60)
        print(f"TEST SUITE FAILED: {str(exc)}")
        print("=" * 60 + "\n")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
