"""
Shared pytest fixtures for LicenseIQ test suite.
All tests use real database connections (integration tests).
"""
import os
import sys
from datetime import UTC, date, datetime

import pytest

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.access import EmployeeWiseRoleMapping, User
from app.models.license import LicenseAllocation
from app.services import aspire as aspire_svc


# ---------------------------------------------------------------------------
# Database session fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db():
    """LicenseIQ database session (shared for the whole test run)."""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def _reset_db_session_state(db):
    """Keep shared DB session usable even if a previous test failed mid-transaction."""
    try:
        db.rollback()
    except Exception:
        pass
    yield
    try:
        db.rollback()
    except Exception:
        pass


@pytest.fixture(scope="session")
def adb():
    """Aspire (read-only) database session (shared for the whole test run)."""
    session = aspire_svc.get_aspire_session()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# Known user fixtures
# ---------------------------------------------------------------------------

KNOWN_USERS = {
    "ramesh":    "122034",   # GDL head (delivery-head role)
    "dharampal": "106949",   # Project Manager
    "cfo":       "112873",   # Finance / CFO
}


@pytest.fixture(scope="session")
def gdl_staffid():
    return KNOWN_USERS["ramesh"]


@pytest.fixture(scope="session")
def pm_staffid():
    return KNOWN_USERS["dharampal"]


@pytest.fixture(scope="session")
def finance_staffid():
    return KNOWN_USERS["cfo"]


# ---------------------------------------------------------------------------
# Role discovery helpers
# ---------------------------------------------------------------------------

def find_role_mapping(db_session, role_code: str):
    """Return the first active EmployeeWiseRoleMapping for a given role code."""
    return db_session.scalar(
        select(EmployeeWiseRoleMapping)
        .where(
            EmployeeWiseRoleMapping.role.has(code=role_code),
            EmployeeWiseRoleMapping.is_active == True,
        )
    )


def find_all_role_mappings(db_session, role_code: str):
    """Return all active EmployeeWiseRoleMappings for a given role code."""
    return list(db_session.scalars(
        select(EmployeeWiseRoleMapping)
        .where(
            EmployeeWiseRoleMapping.role.has(code=role_code),
            EmployeeWiseRoleMapping.is_active == True,
        )
    ).all())


@pytest.fixture(scope="session")
def account_mapping(db):
    return find_role_mapping(db, "account")


@pytest.fixture(scope="session")
def account_owner_staffid(db):
    mapping = find_role_mapping(db, "account") or find_role_mapping(db, "account_owner")
    return mapping.emp_staffid if mapping else None


@pytest.fixture(scope="session")
def gdl_mapping(db):
    return find_role_mapping(db, "gdl")


@pytest.fixture(scope="session")
def pm_mapping(db):
    return find_role_mapping(db, "pm")


# ---------------------------------------------------------------------------
# Additional fixtures for phase3 / phase4 / phase1_sps tests
# ---------------------------------------------------------------------------

from app.models.license import LicenseRequest, ApprovalHistory, LicenseAllocation


def _ensure_test_user(db_session):
    """Return an existing user, or create a deterministic pytest user for FK-safe tests."""
    user = db_session.query(User).order_by(User.id).first()
    if user:
        return user

    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    user = User(
        username=f"pytest_user_{suffix}",
        full_name="Pytest User",
        email=f"pytest_user_{suffix}@licenseiq.local",
        is_active=True,
        aspire_staff_id="PYTEST_FIXTURE",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="session")
def user_id(db):
    """Return the ID of the first active user in the DB."""
    return _ensure_test_user(db).id


@pytest.fixture(scope="session")
def emp_id(db):
    """Return the ID of the first active employee in the DB."""
    from app.models.organization import Employee
    emp = db.query(Employee).filter_by(employment_status="active").first()
    return emp.id if emp else 1


@pytest.fixture(scope="session")
def platform_id(db):
    """Return the ID of the first active platform in the DB."""
    from app.models.platform import Platform
    plat = db.query(Platform).filter_by(is_active=True).first()
    return plat.id if plat else 44


@pytest.fixture(scope="session")
def seed_data(db):
    """Provides known-good IDs for Phase 1 SP tests."""
    from app.models.organization import Employee
    from app.models.platform import Platform

    # Find a valid staff ID with role mapping
    mapping = db.scalar(
        select(EmployeeWiseRoleMapping)
        .where(EmployeeWiseRoleMapping.is_active == True)
        .limit(1)
    )
    staff_id = mapping.emp_staffid if mapping else "108456"

    # Find a valid platform
    plat = db.query(Platform).filter_by(is_active=True).first()
    plat_id = plat.id if plat else 44

    # Find a valid employee
    emp = db.query(Employee).filter_by(employment_status="active").first()
    emp_id_val = emp.id if emp else 1

    # Find or create a valid request for SP lookup tests
    req = db.query(LicenseRequest).first()
    if not req:
        user = _ensure_test_user(db)
        req = LicenseRequest(
            request_type="assign",
            employee_id=emp_id_val,
            platform_id=plat_id,
            requested_by_user_id=user.id,
            requested_by_staffid=staff_id,
            justification="seed_data fixture request",
            effective_date=date.today(),
            approval_status="submitted",
            approval_stage="pending_it_admin",
            last_approver_user_id=user.id,
        )
        db.add(req)
        db.commit()
        db.refresh(req)
    req_id = req.id

    return {
        "platform_id": plat_id,
        "staff_id": staff_id,
        "request_id": req_id,
        "employee_id": emp_id_val,
    }


@pytest.fixture
def benchmark():
    """Fallback benchmark fixture for environments without pytest-benchmark."""
    def _run(func, *args, **kwargs):
        return func(*args, **kwargs)
    return _run


@pytest.fixture
def request_id(db, emp_id, platform_id, user_id):
    """Creates a fresh LicenseRequest in pending_it_admin state for each test."""
    req = LicenseRequest(
        request_type="assign",
        employee_id=emp_id,
        platform_id=platform_id,
        requested_by_user_id=user_id,
        requested_by_staffid="PYTEST_FIXTURE",
        justification="Pytest fixture request",
        effective_date=date.today(),
        approval_status="submitted",
        approval_stage="pending_it_admin",
        last_approver_user_id=user_id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    req_id = req.id
    yield req_id
    # Cleanup
    try:
        db.query(ApprovalHistory).filter(ApprovalHistory.request_id == req_id).delete()
        db.query(LicenseAllocation).filter(
            LicenseAllocation.employee_id == emp_id,
            LicenseAllocation.platform_id == platform_id,
            LicenseAllocation.source_type == "request_approved",
        ).delete()
        req_obj = db.get(LicenseRequest, req_id)
        if req_obj:
            db.delete(req_obj)
        db.commit()
    except Exception:
        db.rollback()
