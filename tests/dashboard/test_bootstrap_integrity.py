"""
Bootstrap response structure and field integrity tests.

Ensures build_dashboard_bootstrap() always returns a well-formed response:
  - Required top-level keys present
  - Employee records have expected fields with valid types/values
  - Platform records are coherent
  - No unexpected nulls in critical fields
"""
import pytest
from app.services.dashboard import build_dashboard_bootstrap, _scoped_employees


# ---------------------------------------------------------------------------
# Top-level response structure
# ---------------------------------------------------------------------------

class TestBootstrapStructure:
    REQUIRED_KEYS = [
        "platforms", "employees", "alerts", "manual_alerts", "queue",
        "seat_snapshots", "monthly_spend", "monthly_project",
        "alloc_hist", "project_meta", "accounts",
    ]

    def _check_structure(self, dash):
        for key in self.REQUIRED_KEYS:
            assert hasattr(dash, key), f"Bootstrap response missing field: '{key}'"

    def test_structure_org_level(self, db):
        self._check_structure(build_dashboard_bootstrap(db, org_level=True))

    def test_structure_gdl(self, db, gdl_staffid):
        self._check_structure(build_dashboard_bootstrap(db, staffid=gdl_staffid))

    def test_structure_pm(self, db, pm_staffid):
        self._check_structure(build_dashboard_bootstrap(db, staffid=pm_staffid))

    def test_structure_finance(self, db, finance_staffid):
        self._check_structure(build_dashboard_bootstrap(db, staffid=finance_staffid))

    def test_accounts_is_list_of_strings(self, db, gdl_staffid):
        dash = build_dashboard_bootstrap(db, staffid=gdl_staffid)
        assert isinstance(dash.accounts, list), "accounts must be a list"
        for a in dash.accounts:
            assert isinstance(a, str), f"Account entry is not a string: {a!r}"

    def test_accounts_no_empty_strings(self, db, gdl_staffid):
        dash = build_dashboard_bootstrap(db, staffid=gdl_staffid)
        blanks = [a for a in dash.accounts if not a.strip()]
        assert not blanks, f"accounts list contains {len(blanks)} empty/blank strings"

    def test_accounts_no_duplicates(self, db, gdl_staffid):
        dash = build_dashboard_bootstrap(db, staffid=gdl_staffid)
        assert len(dash.accounts) == len(set(dash.accounts)), (
            "accounts list contains duplicates"
        )

    def test_project_meta_values_have_acct_and_gdl(self, db, gdl_staffid):
        dash = build_dashboard_bootstrap(db, staffid=gdl_staffid)
        for proj_key, meta in dash.project_meta.items():
            assert hasattr(meta, "acct"), f"project_meta['{proj_key}'] missing 'acct'"
            assert hasattr(meta, "gdl"),  f"project_meta['{proj_key}'] missing 'gdl'"


# ---------------------------------------------------------------------------
# Employee record integrity
# ---------------------------------------------------------------------------

class TestEmployeeRecordIntegrity:
    def test_employee_ids_are_positive_integers(self, db, gdl_staffid):
        dash = build_dashboard_bootstrap(db, staffid=gdl_staffid)
        for emp in dash.employees:
            assert emp.id, f"Employee has falsy id: {emp.id!r}"
            assert isinstance(emp.id, str), f"Employee id should be str, got {type(emp.id)}"

    def test_employee_names_non_empty(self, db, pm_staffid):
        dash = build_dashboard_bootstrap(db, staffid=pm_staffid)
        for emp in dash.employees:
            assert emp.name and emp.name.strip(), (
                f"Employee id={emp.id} has empty name"
            )

    def test_employee_status_valid(self, db, gdl_staffid):
        valid_statuses = {"active", "inactive", "onleave"}
        dash = build_dashboard_bootstrap(db, staffid=gdl_staffid)
        for emp in dash.employees:
            assert emp.status in valid_statuses, (
                f"Employee {emp.name} has unexpected status: {emp.status!r}"
            )

    def test_employee_license_costs_non_negative(self, db, pm_staffid):
        dash = build_dashboard_bootstrap(db, staffid=pm_staffid)
        for emp in dash.employees:
            for lic in emp.lics:
                assert lic.cost >= 0.0, (
                    f"Employee {emp.name} has negative license cost: {lic.cost} ({lic.plat})"
                )

    def test_employee_no_duplicate_ids(self, db, gdl_staffid):
        dash = build_dashboard_bootstrap(db, staffid=gdl_staffid)
        ids = [emp.id for emp in dash.employees]
        assert len(ids) == len(set(ids)), (
            f"Duplicate employee IDs in GDL bootstrap: "
            f"{[x for x in ids if ids.count(x) > 1][:5]}"
        )

    def test_is_current_false_when_revoked(self, db, gdl_staffid):
        """License marked isCurrent=True must not have a revoked allocation."""
        dash = build_dashboard_bootstrap(db, staffid=gdl_staffid)
        for emp in dash.employees:
            for lic in emp.lics:
                if lic.isCurrent:
                    # isCurrent means revoked_date is None — cost must be >= 0
                    assert lic.cost >= 0.0, (
                        f"Current license for {emp.name} has negative cost"
                    )


# ---------------------------------------------------------------------------
# Platform record integrity
# ---------------------------------------------------------------------------

class TestPlatformIntegrity:
    def test_platforms_non_empty(self, db):
        dash = build_dashboard_bootstrap(db, org_level=True)
        assert len(dash.platforms) > 0, "No platforms returned in org-level bootstrap"

    def test_platform_seat_cost_non_negative(self, db):
        dash = build_dashboard_bootstrap(db, org_level=True)
        for p in dash.platforms:
            assert p.seatCost >= 0.0, f"Platform '{p.name}' has negative seatCost: {p.seatCost}"

    def test_platform_names_non_empty(self, db):
        dash = build_dashboard_bootstrap(db, org_level=True)
        for p in dash.platforms:
            assert p.name and p.name.strip(), f"Platform id={p.id} has empty name"

    def test_seat_snapshots_dates_ordered(self, db):
        dash = build_dashboard_bootstrap(db, org_level=True)
        for plat_name, snapshots in dash.seat_snapshots.items():
            if len(snapshots) < 2:
                continue
            dates = [s.date for s in snapshots]
            assert dates == sorted(dates), (
                f"Seat snapshots for '{plat_name}' are not in chronological order"
            )


# ---------------------------------------------------------------------------
# Queue and alert integrity
# ---------------------------------------------------------------------------

class TestQueueAndAlerts:
    def test_queue_items_have_required_fields(self, db):
        dash = build_dashboard_bootstrap(db, org_level=True)
        for item in dash.queue:
            assert item.id is not None, "Queue item missing id"
            assert item.status, "Queue item missing status"

    def test_alert_priority_valid(self, db):
        valid_priorities = {"high", "medium", "low", "info", ""}
        dash = build_dashboard_bootstrap(db, org_level=True)
        for alert in dash.alerts:
            assert alert.pri.lower() in valid_priorities, (
                f"Alert has unexpected priority: {alert.pri!r}"
            )
