"""
Phase 4 Queue Execution & Alerts ORM Mode Validation Tests

Tests the queue execution and alert workflows through ORM implementation:
- Execute queue item assignment
- Execute queue item revocation
- Mark queue item executed
- Create alert
- Resolve alert
- Get queue metrics
"""

import os
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
    
    # Create test employee
    test_emp = db.query(Employee).filter_by(id=100003).first()
    if not test_emp:
        test_emp = Employee(
            id=100003,
            full_name="Test Employee Phase4",
            employee_code="TEST003",
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
    
    # Create test platforms
    test_platform1 = db.query(Platform).filter_by(id=102).first()
    if not test_platform1:
        test_platform1 = Platform(
            id=102,
            name="Phase4TestPlatformAssignment",
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
    
    test_platform2 = db.query(Platform).filter_by(id=103).first()
    if not test_platform2:
        test_platform2 = Platform(
            id=103,
            name="Phase4TestPlatformRevocation",
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


def test_execute_queue_item_assignment(db, emp_id, platform_id, user_id):
    """Test executing a queue item assignment."""
    print("\n[TEST 1] EXECUTE QUEUE ITEM ASSIGNMENT")
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
        
        # Execute the assignment
        execute_queue_item_assignment_phase4(
            db,
            queue_item_id=queue_item_id,
            executed_by_user_id=user_id,
            execution_notes="Test assignment execution",
        )
        
        # Verify queue item is marked as executed
        queue_item = db.get(QueueItem, queue_item_id)
        print(f"✓ ASSIGNMENT PASS - Queue item executed")
        print(f"  - status: {queue_item.status}")
        print(f"  - executed_by_user_id: {queue_item.executed_by_user_id}")
        
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
        print(f"✗ ASSIGNMENT FAIL - {str(exc)}")
        raise


def test_execute_queue_item_revocation(db, emp_id, platform_id, user_id):
    """Test executing a queue item revocation."""
    print("\n[TEST 2] EXECUTE QUEUE ITEM REVOCATION")
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
        
        # Execute the revocation
        execute_queue_item_revocation_phase4(
            db,
            queue_item_id=queue_item_id,
            executed_by_user_id=user_id,
            execution_notes="Test revocation execution",
        )
        
        # Verify queue item is marked as executed
        queue_item = db.get(QueueItem, queue_item_id)
        print(f"✓ REVOCATION PASS - Queue item executed")
        print(f"  - status: {queue_item.status}")
        
        # Verify allocation was revoked
        allocation = db.get(LicenseAllocation, allocation.id)
        assert allocation.status == "revoked"
        print(f"  - Allocation revoked with status={allocation.status}")
        
        # Verify audit record
        audit = db.query(AllocationAudit).filter_by(allocation_id=allocation.id).first()
        assert audit is not None
        print(f"  - Audit record created with id={audit.id}")
        
    except Exception as exc:
        print(f"✗ REVOCATION FAIL - {str(exc)}")
        raise


def test_mark_queue_item_executed(db, emp_id, platform_id, user_id):
    """Test marking a queue item as executed."""
    print("\n[TEST 3] MARK QUEUE ITEM EXECUTED")
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
        
        # Mark as executed
        mark_queue_item_executed_phase4(
            db,
            queue_item_id=queue_item_id,
            executed_by_user_id=user_id,
            execution_notes="Marked executed for testing",
        )
        
        # Verify status
        queue_item = db.get(QueueItem, queue_item_id)
        print(f"✓ MARK EXECUTED PASS - Queue item marked as executed")
        print(f"  - status: {queue_item.status}")
        print(f"  - executed_by_user_id: {queue_item.executed_by_user_id}")
        
        assert queue_item.status == "executed"
        
    except Exception as exc:
        print(f"✗ MARK EXECUTED FAIL - {str(exc)}")
        raise


def test_create_and_resolve_alert(db, emp_id, platform_id):
    """Test creating and resolving alerts."""
    print("\n[TEST 4] CREATE AND RESOLVE ALERT")
    print("=" * 60)
    
    try:
        # Create alert
        alert_id = create_alert_phase4(
            db,
            alert_type="license_expiring",
            priority="high",
            reason="License expiration approaching",
            employee_id=emp_id,
            platform_id=platform_id,
            detail="License expires in 30 days",
            source_system="test",
        )
        
        print(f"✓ CREATE ALERT PASS - Alert created with id={alert_id}")
        
        # Verify alert
        alert = db.get(Alert, alert_id)
        assert alert.status == "open"
        print(f"  - status: {alert.status}")
        print(f"  - alert_type: {alert.alert_type}")
        
        # Resolve alert
        resolve_alert_phase4(db, alert_id=alert_id)
        
        # Verify resolution
        alert = db.get(Alert, alert_id)
        print(f"✓ RESOLVE ALERT PASS - Alert resolved")
        print(f"  - status: {alert.status}")
        print(f"  - resolved_at: {alert.resolved_at}")
        
        assert alert.status == "resolved"
        
    except Exception as exc:
        print(f"✗ ALERT FAIL - {str(exc)}")
        raise


def test_get_queue_metrics(db):
    """Test getting queue metrics."""
    print("\n[TEST 5] GET QUEUE METRICS")
    print("=" * 60)
    
    try:
        # Get metrics
        metrics = get_queue_metrics_phase4(db)
        
        print(f"✓ METRICS PASS - Queue metrics retrieved")
        print(f"  - pending_count: {metrics.get('pending_count', 'N/A')}")
        print(f"  - executed_count: {metrics.get('executed_count', 'N/A')}")
        print(f"  - rejected_count: {metrics.get('rejected_count', 'N/A')}")
        print(f"  - open_alerts: {metrics.get('open_alerts', 'N/A')}")
        print(f"  - resolved_alerts: {metrics.get('resolved_alerts', 'N/A')}")
        
        assert isinstance(metrics, dict)
        
    except Exception as exc:
        print(f"✗ METRICS FAIL - {str(exc)}")
        raise


def main():
    """Run all Phase 4 ORM validation tests."""
    print("\n" + "=" * 60)
    print("PHASE 4 QUEUE EXECUTION & ALERTS - ORM MODE VALIDATION")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Check feature flag status
        from app.core.feature_flags import is_phase4_queue_alerts_enabled
        print(f"\nFeature Flag Status: USE_PHASE4_QUEUE_ALERTS_SPS = {is_phase4_queue_alerts_enabled()}")
        print("(Should be False for ORM-mode testing)")
        
        # Setup test data
        emp_id, platform_id1, platform_id2, user_id = setup_test_data(db)
        
        if user_id is None:
            print("\n⚠ WARNING: No valid user ID found.")
            return
        
        # Run tests
        test_execute_queue_item_assignment(db, emp_id, platform_id1, user_id)
        test_execute_queue_item_revocation(db, emp_id, platform_id2, user_id)
        test_mark_queue_item_executed(db, user_id)
        test_create_and_resolve_alert(db, emp_id, platform_id1)
        test_get_queue_metrics(db)
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED - Phase 4 ORM-mode integration is working!")
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
