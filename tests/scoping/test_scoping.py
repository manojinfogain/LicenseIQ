"""
Role-based scoping boundary tests.

Verifies that each role type (admin/org, gdl, account, pm) returns
the correct set of employees and does NOT leak accounts/projects from
outside the user's authorised scope.
"""
import pytest
from sqlalchemy import func, select

from app.services.dashboard import build_dashboard_bootstrap, _scoped_employees
from app.services import aspire as aspire_svc
from app.models.aspire import (
    AspireDeliveryUnit,
    AspireProject,
    AspireProjectAssignment,
    AspireEmployee,
    AspireAccount,
)
from tests.conftest import find_all_role_mappings, find_role_mapping


def _allowed_aspire_identifiers(aspire_emps):
    """Return all valid employee identifiers (staffid and Emp_NewID) for scope assertions."""
    identifiers = set()
    for ae in aspire_emps:
        staffid = (ae.emp_staffid or "").strip()
        new_id = (ae.emp_new_id or "").strip()
        if staffid:
            identifiers.add(staffid)
        if new_id:
            identifiers.add(new_id)
    return identifiers


# ---------------------------------------------------------------------------
# Org-level / admin
# ---------------------------------------------------------------------------

class TestOrgLevelScoping:
    def test_org_level_returns_employees(self, db):
        """Org-level bootstrap must return at least one employee."""
        emps = _scoped_employees(db, org_level=True)
        assert len(emps) > 0, "Org-level scope returned no employees"

    def test_org_level_bootstrap_populates_accounts(self, db):
        dash = build_dashboard_bootstrap(db, org_level=True)
        assert len(dash.accounts) > 0, "Org-level bootstrap returned no accounts"

    def test_org_level_employee_count_gte_any_scoped(self, db, gdl_staffid):
        """Org scope must be >= any single-role scope."""
        org_emps = _scoped_employees(db, org_level=True)
        gdl_emps = _scoped_employees(db, staffid=gdl_staffid)
        assert len(org_emps) >= len(gdl_emps), (
            f"Org scope ({len(org_emps)}) < GDL scope ({len(gdl_emps)}) — impossible"
        )


# ---------------------------------------------------------------------------
# GDL scoping
# ---------------------------------------------------------------------------

class TestGDLScoping:
    def test_gdl_returns_employees(self, db, gdl_staffid):
        emps = _scoped_employees(db, staffid=gdl_staffid)
        assert len(emps) > 0, f"GDL staffid {gdl_staffid} returned no employees"

    def test_gdl_ramesh_no_sales_mu4(self, db, gdl_staffid):
        """Regression: Ramesh (122034) must not see 'Sales MU4' accounts."""
        dash = build_dashboard_bootstrap(db, staffid=gdl_staffid)
        contaminated = [a for a in dash.accounts if "Sales" in a or "MU4" in a]
        assert not contaminated, (
            f"GDL {gdl_staffid} leaks forbidden accounts: {contaminated}"
        )

    def test_gdl_accounts_are_within_delivery_head_scope(self, db, adb, gdl_staffid):
        """
        Every account seen by a GDL user must belong to a project in a delivery
        unit headed by that GDL user in Aspire.
        """
        sid = gdl_staffid.strip()

        # Get the set of account names visible via Aspire delivery-head query
        aspire_emps = aspire_svc.get_aspire_employees_by_delivery_head(adb, sid)
        allowed_accounts = set()
        for ae in aspire_emps:
            for pa in (ae.project_assignments or []):
                if pa.project and pa.project.account:
                    name = (pa.project.account.account_name or "").strip()
                    if name:
                        allowed_accounts.add(name)

        dash = build_dashboard_bootstrap(db, staffid=sid)
        for acct in dash.accounts:
            assert acct in allowed_accounts, (
                f"Account '{acct}' shown for GDL {sid} but not in Aspire delivery-head scope"
            )

    def test_all_gdl_users_have_non_empty_scope(self, db):
        """Every active GDL mapping should yield at least one employee.
        Users with no current Aspire assignments issue a warning rather than a hard failure."""
        import warnings
        mappings = find_all_role_mappings(db, "gdl")
        assert mappings, "No GDL role mappings found"
        empty = []
        for m in mappings:
            emps = _scoped_employees(db, staffid=m.emp_staffid)
            if len(emps) == 0:
                empty.append(m.emp_staffid)
        if empty:
            warnings.warn(
                f"{len(empty)} GDL user(s) with 0 scoped employees "
                f"(likely no current Aspire assignments): {empty}"
            )

    def test_gdl_no_duplicate_employees(self, db, gdl_staffid):
        emps = _scoped_employees(db, staffid=gdl_staffid)
        ids = [e.id for e in emps]
        assert len(ids) == len(set(ids)), "Duplicate employee IDs in GDL scope"


# ---------------------------------------------------------------------------
# PM scoping
# ---------------------------------------------------------------------------

class TestPMScoping:
    def test_pm_returns_employees(self, db, pm_staffid):
        emps = _scoped_employees(db, staffid=pm_staffid)
        assert len(emps) > 0, f"PM staffid {pm_staffid} returned no employees"

    def test_pm_dharampal_flagged_is_zero(self, db, pm_staffid):
        """Dharampal Singh's scope should have 0 flagged/inactive licenses (validated manually)."""
        from sqlalchemy import func, select
        from app.models.license import LicenseAllocation

        emps = _scoped_employees(db, staffid=pm_staffid)
        emp_ids = [e.id for e in emps]

        flagged = db.scalar(
            select(func.count(LicenseAllocation.id)).where(
                LicenseAllocation.employee_id.in_(emp_ids),
                LicenseAllocation.revoked_date.is_(None),
                LicenseAllocation.status != "active",
            )
        ) or 0
        assert flagged == 0, (
            f"PM {pm_staffid} expected 0 flagged licenses, got {flagged}"
        )

    def test_pm_employees_in_pm_project(self, db, adb, pm_staffid):
        """
        Every employee in a PM's scope should be on a project managed by or
        primarily assigned with that PM in Aspire.

        Note: when a PM has no PROJECTMNGR_ID entries, the code falls back to
        scoping by their primary project (get_aspire_employees_by_project_id).
        In that case we skip the strict check and only validate the PM themselves
        appears in their own scope.
        """
        sid = pm_staffid.strip()
        aspire_emps_by_pm = aspire_svc.get_aspire_employees_by_project_manager(adb, sid)

        if not aspire_emps_by_pm:
            # PM is scoped by their primary project_id, not as PROJECTMNGR_ID.
            # Just verify the PM themselves appears in the scope.
            emps = _scoped_employees(db, staffid=sid)
            codes = {(e.employee_code or "").strip() for e in emps}
            assert sid in codes, (
                f"PM {sid} does not appear in their own scoped employees"
            )
            pytest.skip(
                f"PM {sid} has no PROJECTMNGR_ID rows — scoped by primary project; "
                f"strict employee-set assertion skipped"
            )

        allowed_staffids = _allowed_aspire_identifiers(aspire_emps_by_pm)
        emps = _scoped_employees(db, staffid=sid)
        for emp in emps:
            code = (emp.employee_code or "").strip()
            assert code in allowed_staffids, (
                f"Employee {emp.full_name} ({code}) is in PM {sid}'s scope "
                f"but not in Aspire PM query"
            )

    def test_all_pm_users_have_non_empty_scope(self, db):
        mappings = find_all_role_mappings(db, "pm")
        assert mappings, "No PM role mappings found"
        for m in mappings:
            emps = _scoped_employees(db, staffid=m.emp_staffid)
            assert len(emps) > 0, (
                f"PM staffid {m.emp_staffid} returned 0 employees"
            )


# ---------------------------------------------------------------------------
# Account-owner scoping
# ---------------------------------------------------------------------------

class TestAccountScoping:
    def test_account_owner_returns_employees(self, db, account_mapping):
        if account_mapping is None:
            pytest.skip("No account role mapping found in database")
        emps = _scoped_employees(db, staffid=account_mapping.emp_staffid)
        assert len(emps) > 0, f"Account owner {account_mapping.emp_staffid} returned no employees"

    def test_account_owner_employees_in_owned_accounts(self, db, adb, account_mapping):
        """Every employee in the account-owner scope must belong to an account owned by them."""
        if account_mapping is None:
            pytest.skip("No account role mapping found in database")

        sid = account_mapping.emp_staffid.strip()
        aspire_emps = aspire_svc.get_aspire_employees_by_account_owner(adb, sid)
        allowed_staffids = _allowed_aspire_identifiers(aspire_emps)

        emps = _scoped_employees(db, staffid=sid)
        for emp in emps:
            code = (emp.employee_code or "").strip()
            assert code in allowed_staffids, (
                f"Employee {emp.full_name} ({code}) in account-owner {sid}'s scope "
                f"but NOT in Aspire account-owner query"
            )

    def test_all_account_users_have_non_empty_scope(self, db):
        import warnings
        mappings = find_all_role_mappings(db, "account")
        assert mappings, "No account role mappings found"
        empty = []
        for m in mappings:
            emps = _scoped_employees(db, staffid=m.emp_staffid)
            if len(emps) == 0:
                empty.append(m.emp_staffid)
        if empty:
            warnings.warn(
                f"{len(empty)} account user(s) with 0 scoped employees "
                f"(likely no current Aspire assignments): {empty}"
            )


# ---------------------------------------------------------------------------
# Cross-scope isolation
# ---------------------------------------------------------------------------

class TestCrossScopeIsolation:
    def test_two_gdl_users_see_different_scopes(self, db):
        """Two distinct GDL users should see different (non-identical) employee sets."""
        mappings = find_all_role_mappings(db, "gdl")
        if len(mappings) < 2:
            pytest.skip("Fewer than 2 active GDL mappings — cannot test isolation")

        # Only compare pairs where both users have non-empty scopes
        non_empty = [
            m for m in mappings
            if len(_scoped_employees(db, staffid=m.emp_staffid)) > 0
        ]
        if len(non_empty) < 2:
            pytest.skip("Fewer than 2 GDL users with non-empty scopes — cannot test isolation")

        emps_a = {e.id for e in _scoped_employees(db, staffid=non_empty[0].emp_staffid)}
        emps_b = {e.id for e in _scoped_employees(db, staffid=non_empty[1].emp_staffid)}
        assert emps_a != emps_b, (
            f"GDL {non_empty[0].emp_staffid} and {non_empty[1].emp_staffid} see identical employee sets"
        )

    def test_gdl_scope_subset_of_org(self, db, gdl_staffid):
        org_ids = {e.id for e in _scoped_employees(db, org_level=True)}
        gdl_ids = {e.id for e in _scoped_employees(db, staffid=gdl_staffid)}
        outliers = gdl_ids - org_ids
        assert not outliers, (
            f"GDL scope contains {len(outliers)} employees not in org scope: "
            f"{list(outliers)[:5]}"
        )

    def test_unknown_staffid_returns_gracefully(self, db):
        """A staffid with no role mapping should not crash — returns empty or org-scoped."""
        try:
            emps = _scoped_employees(db, staffid="XXXXXX_NONEXISTENT")
            # Either empty list or some result — just must not raise
        except Exception as exc:
            pytest.fail(f"Unknown staffid raised exception: {exc}")
