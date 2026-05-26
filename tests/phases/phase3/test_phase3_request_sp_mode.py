"""
Phase 3 Request Lifecycle SP Mode Validation Tests

Tests the complete request workflow through stored procedure implementation
when Phase 3 feature flag is enabled:
- Create request (via SP)
- Approve request (via SP)
- Final approve request (via SP)
- Reject request (via SP)
"""

import os
import sys
from datetime import datetime, date

# Enable Phase 3 feature flag
os.environ["USE_PHASE3_REQUEST_SPS"] = "true"

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from app.core.database import SessionLocal
from app.models.organization import Employee, Account, Project
from app.models.platform import Platform
from app.models.license import LicenseRequest, ApprovalHistory, LicenseAllocation
from app.models.access import User
from app.schemas.request import LicenseRequestCreate
from app.services.phase3_integration import (
    create_license_request_phase3,
    approve_license_request_phase3,
    final_approve_license_request_phase3,
    reject_license_request_phase3,
)


def setup_test_data(db):
    """Create test data: employees, platforms, users."""
    print("\n[SETUP] Creating test data...")
    
    # Create test user (approver)
    approver = db.query(User).filter_by(id=1).first()
    if not approver:
        existing_users = db.query(User).limit(1).all()
        if existing_users:
            approver_id = existing_users[0].id
            print(f"  Using existing user ID: {approver_id}")
        else:
            print("  WARNING: No users found in database")
            approver_id = None
    else:
        approver_id = approver.id
        print(f"  Using approver user ID: {approver_id}")
    
    # Get or create test account
    test_account = db.query(Account).filter_by(id=1).first()
    if not test_account:
        test_account = Account(name="Test Account SP", status="active")
        db.add(test_account)
        db.flush()
        print(f"  Created test account ID: {test_account.id}")
    else:
        print(f"  Using existing account ID: {test_account.id}")
    
    # Get or create test project
    test_project = db.query(Project).filter_by(id=1).first()
    if not test_project:
        test_project = Project(name="Test Project SP", account_id=test_account.id, status="active")
        db.add(test_project)
        db.flush()
        print(f"  Created test project ID: {test_project.id}")
    else:
        print(f"  Using existing project ID: {test_project.id}")
    
    # Create test employee
    test_emp = db.query(Employee).filter_by(id=100002).first()
    if not test_emp:
        test_emp = Employee(
            id=100002,
            full_name="Test Employee SP",
            employee_code="TEST002",
            unit="Testing",
            employment_status="active",
            account_id=test_account.id,
            project_id=test_project.id,
            account_owner_user_id=approver_id,
        )
        db.add(test_emp)
        db.flush()
        print(f"  Created test employee ID: {test_emp.id}")
    else:
        print(f"  Using existing employee ID: {test_emp.id}")
    
    # Create test platform
    test_platform = db.query(Platform).filter_by(id=101).first()
    if not test_platform:
        test_platform = Platform(
            id=101,
            name="Phase3TestPlatformSP",
            vendor="TestVendor",
            category="Development",
            agreement_type="perpetual",
            license_type="named_user",
            billing_period="annual",
            currency="USD",
            is_active=True,
        )
        db.add(test_platform)
        db.flush()
        print(f"  Created test platform ID: {test_platform.id}")
    else:
        print(f"  Using existing platform ID: {test_platform.id}")
    
    db.commit()
    return test_emp.id, test_platform.id, approver_id


def test_create_license_request_sp(db, emp_id, platform_id, user_id):
    """Test creating a license request via SP."""
    print("\n[TEST 1] CREATE LICENSE REQUEST (SP MODE)")
    print("=" * 60)
    
    try:
        payload = LicenseRequestCreate(
            request_type="assign",
            employee_id=emp_id,
            platform_id=platform_id,
            project_id=None,
            account_id=None,
            requested_by_user_id=user_id,
            requested_by_staffid="TEST_USER_SP",
            justification="Test SP license request creation",
            effective_date=date.today(),
        )
        
        # Create request using Phase 3 SP (flag is enabled)
        request = create_license_request_phase3(db, payload)
        
        print(f"✓ CREATE PASS - Platform created with id={request.id}")
        print(f"  - request_type: {request.request_type}")
        print(f"  - employee_id: {request.employee_id}")
        print(f"  - platform_id: {request.platform_id}")
        print(f"  - approval_status: {request.approval_status}")
        print(f"  - approval_stage: {request.approval_stage}")
        
        assert request.id is not None
        assert request.approval_status == "submitted"
        assert request.approval_stage == "pending_account_owner"
        
        return request.id
    except Exception as exc:
        print(f"✗ CREATE FAIL - {str(exc)}")
        raise


def test_approve_license_request_sp(db, request_id, user_id):
    """Test first-level approval via SP."""
    print("\n[TEST 2] APPROVE LICENSE REQUEST (SP MODE)")
    print("=" * 60)
    
    try:
        request = approve_license_request_phase3(
            db,
            request_id=request_id,
            approver_user_id=user_id,
            approver_role="account_owner",
            approval_notes="Approved by account owner via SP",
            action="approved",
        )
        
        print(f"✓ APPROVE PASS - Request approved")
        print(f"  - approval_stage: {request.approval_stage}")
        print(f"  - approval_status: {request.approval_status}")
        print(f"  - last_approver_user_id: {request.last_approver_user_id}")
        
        assert request.approval_stage == "pending_it_admin"
        assert request.last_approver_user_id == user_id
        
        history = db.query(ApprovalHistory).filter_by(request_id=request_id).first()
        assert history is not None
        assert history.action == "approved"
        print(f"  - Approval history created: id={history.id}")
        
    except Exception as exc:
        print(f"✗ APPROVE FAIL - {str(exc)}")
        raise


def test_final_approve_license_request_sp(db, request_id, user_id):
    """Test final approval and allocation creation via SP."""
    print("\n[TEST 3] FINAL APPROVE LICENSE REQUEST (SP MODE)")
    print("=" * 60)
    
    try:
        request_before = db.query(LicenseRequest).filter_by(id=request_id).first()
        emp_id = request_before.employee_id
        platform_id = request_before.platform_id
        print(f"  Before: stage={request_before.approval_stage}, status={request_before.approval_status}")
        
        request = final_approve_license_request_phase3(
            db,
            request_id=request_id,
            approver_user_id=user_id,
            approver_role="it_admin",
            approval_notes="Final approval by IT admin via SP",
            action="approved",
        )
        
        print(f"✓ FINAL APPROVE PASS - Request finalized")
        print(f"  - approval_status: {request.approval_status}")
        print(f"  - approval_stage: {request.approval_stage}")
        
        assert request.approval_status == "approved"
        assert request.approval_stage == "approved"
        
        allocation = db.query(LicenseAllocation).filter_by(
            employee_id=emp_id,
            platform_id=platform_id,
            status="active",
            source_type="request_approved",
        ).first()
        assert allocation is not None
        assert allocation.source_type == "request_approved"
        print(f"  - License allocation created: id={allocation.id}")
        
    except Exception as exc:
        print(f"✗ FINAL APPROVE FAIL - {str(exc)}")
        raise


def test_reject_license_request_sp(db, emp_id, platform_id, user_id):
    """Test rejecting a license request via SP."""
    print("\n[TEST 4] REJECT LICENSE REQUEST (SP MODE)")
    print("=" * 60)
    
    try:
        payload = LicenseRequestCreate(
            request_type="assign",
            employee_id=emp_id,
            platform_id=platform_id,
            project_id=None,
            account_id=None,
            requested_by_user_id=user_id,
            requested_by_staffid="TEST_USER_REJECT_SP",
            justification="Test SP license request rejection",
            effective_date=date.today(),
        )
        
        request = create_license_request_phase3(db, payload)
        reject_request_id = request.id
        
        print(f"  Created test request ID: {reject_request_id}")
        print(f"  Before: stage={request.approval_stage}, status={request.approval_status}")
        
        request = reject_license_request_phase3(
            db,
            request_id=reject_request_id,
            rejecter_user_id=user_id,
            rejecter_role="account_owner",
            rejection_reason="Rejected for testing purposes via SP",
        )
        
        print(f"✓ REJECT PASS - Request rejected")
        print(f"  - approval_status: {request.approval_status}")
        print(f"  - approval_stage: {request.approval_stage}")
        
        assert request.approval_status == "rejected"
        assert request.approval_stage == "rejected"
        
        history = db.query(ApprovalHistory).filter_by(request_id=reject_request_id).first()
        assert history is not None
        assert history.action == "rejected"
        print(f"  - Rejection history created: id={history.id}")
        
    except Exception as exc:
        print(f"✗ REJECT FAIL - {str(exc)}")
        raise


def main():
    """Run all Phase 3 SP validation tests."""
    print("\n" + "=" * 60)
    print("PHASE 3 REQUEST LIFECYCLE - SP MODE VALIDATION")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Verify feature flag is enabled
        from app.core.feature_flags import is_phase3_request_enabled
        print(f"\nFeature Flag Status: USE_PHASE3_REQUEST_SPS = {is_phase3_request_enabled()}")
        if not is_phase3_request_enabled():
            print("ERROR: Feature flag should be True for SP-mode testing!")
            sys.exit(1)
        
        # Setup test data
        emp_id, platform_id, user_id = setup_test_data(db)
        
        if user_id is None:
            print("\n⚠ WARNING: No valid user ID found. Skipping tests.")
            return
        
        # Run tests
        request_id = test_create_license_request_sp(db, emp_id, platform_id, user_id)
        test_approve_license_request_sp(db, request_id, user_id)
        test_final_approve_license_request_sp(db, request_id, user_id)
        test_reject_license_request_sp(db, emp_id, platform_id, user_id)
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED - Phase 3 SP mode is working!")
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
