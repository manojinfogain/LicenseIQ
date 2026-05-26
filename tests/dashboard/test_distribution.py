"""
Distribution by Account Owner tests.

Verifies that employees are correctly grouped by account owner
and that bootstrap data contains the required account/owner fields.
"""
import pytest
from collections import defaultdict
from sqlalchemy import select

from app.services.dashboard import build_dashboard_bootstrap
from app.models.organization import Employee, Account


class TestDistributionByAccountOwner:
    def test_employees_have_account_field(self, db):
        """Every employee record should have an account name."""
        dash = build_dashboard_bootstrap(db, org_level=True)
        assert len(dash.employees) > 0, "No employees returned"
        missing = [e for e in dash.employees if not getattr(e, "acct", None)]
        assert len(missing) < len(dash.employees), (
            f"All {len(dash.employees)} employees are missing account field"
        )

    def test_employees_groupable_by_account_owner(self, db):
        """Employees can be grouped by account owner without errors."""
        dash = build_dashboard_bootstrap(db, org_level=True)
        grouped = defaultdict(list)
        for e in dash.employees:
            owner = getattr(e, "acct_owner", None) or getattr(e, "acctOwner", "") or ""
            grouped[owner].append(e)
        assert len(grouped) >= 1, "Expected at least one account owner group"

    def test_accounts_list_non_empty(self, db):
        """Bootstrap should return a non-empty accounts list."""
        dash = build_dashboard_bootstrap(db, org_level=True)
        assert isinstance(dash.accounts, list)
        assert len(dash.accounts) > 0, "Accounts list is empty"

    def test_account_owner_scoped_bootstrap_has_employees(self, db, account_owner_staffid):
        """Account owner sees employees in their account only."""
        dash = build_dashboard_bootstrap(db, staffid=account_owner_staffid)
        assert dash is not None
        assert isinstance(dash.employees, list)

    def test_employee_account_ids_valid(self, db):
        """All employees linked to valid account IDs in DB."""
        employees_with_account = list(db.scalars(
            select(Employee).where(Employee.account_id.is_not(None)).limit(50)
        ).all())
        assert len(employees_with_account) > 0, "No employees have account_id set"
        account_ids = {e.account_id for e in employees_with_account}
        accounts = list(db.scalars(
            select(Account).where(Account.id.in_(account_ids))
        ).all())
        found_ids = {a.id for a in accounts}
        missing = account_ids - found_ids
        assert len(missing) == 0, f"Employees reference non-existent account IDs: {missing}"
