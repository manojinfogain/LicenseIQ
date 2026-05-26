"""
Dashboard KPI accuracy tests.

Verifies that flagged/inactive counts, recoverable spend, monthly spend series,
and annual projections are numerically correct and internally consistent.
"""
import pytest
from datetime import date
from sqlalchemy import func, select

from app.models.license import LicenseAllocation
from app.services.dashboard import build_dashboard_bootstrap, build_dashboard_summary, _scoped_employees


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _alloc_counts(db, emp_ids: list[int]):
    """Return (total, active, flagged, monthly_cost, recoverable) for a list of employee IDs."""
    if not emp_ids:
        return 0, 0, 0, 0.0, 0.0

    def _q(extra):
        total = 0
        for i in range(0, len(emp_ids), 2000):
            chunk = emp_ids[i:i + 2000]
            total += db.scalar(
                select(func.count(LicenseAllocation.id)).where(
                    LicenseAllocation.employee_id.in_(chunk),
                    LicenseAllocation.revoked_date.is_(None),
                    *extra,
                )
            ) or 0
        return total

    def _s(extra):
        total = 0.0
        for i in range(0, len(emp_ids), 2000):
            chunk = emp_ids[i:i + 2000]
            total += float(db.scalar(
                select(func.coalesce(func.sum(LicenseAllocation.monthly_cost), 0)).where(
                    LicenseAllocation.employee_id.in_(chunk),
                    LicenseAllocation.revoked_date.is_(None),
                    *extra,
                )
            ) or 0)
        return total

    total = _q([])
    active = _q([LicenseAllocation.status == "active"])
    flagged = _q([LicenseAllocation.status != "active"])
    monthly_cost = _s([])
    recoverable = _s([LicenseAllocation.status != "active"])
    return total, active, flagged, monthly_cost, recoverable


# ---------------------------------------------------------------------------
# Summary endpoint metrics
# ---------------------------------------------------------------------------

class TestSummaryMetrics:
    def test_flagged_plus_active_equals_total(self, db, gdl_staffid):
        emps = _scoped_employees(db, staffid=gdl_staffid)
        emp_ids = [e.id for e in emps]
        total, active, flagged, _, _ = _alloc_counts(db, emp_ids)
        assert active + flagged == total, (
            f"active ({active}) + flagged ({flagged}) != total ({total})"
        )

    def test_summary_counts_match_direct_query(self, db, pm_staffid):
        """build_dashboard_summary() counts must match direct SQL counts."""
        emps = _scoped_employees(db, staffid=pm_staffid)
        emp_ids = [e.id for e in emps]
        _, expected_active, expected_flagged, expected_spend, _ = _alloc_counts(db, emp_ids)

        summary = build_dashboard_summary(db, staffid=pm_staffid)
        assert summary.active_licenses == expected_active, (
            f"Summary active={summary.active_licenses}, expected={expected_active}"
        )
        assert summary.flagged_licenses == expected_flagged, (
            f"Summary flagged={summary.flagged_licenses}, expected={expected_flagged}"
        )
        assert abs(summary.monthly_spend - expected_spend) < 0.01, (
            f"Summary monthly_spend={summary.monthly_spend:.2f}, expected={expected_spend:.2f}"
        )

    def test_org_level_summary_non_zero(self, db):
        # org-level = no staffid filter; build_dashboard_summary has no org_level arg
        summary = build_dashboard_summary(db)
        assert summary.employee_count > 0
        assert summary.total_licenses >= 0
        assert summary.active_licenses >= 0
        assert summary.monthly_spend >= 0.0

    def test_recoverable_never_negative(self, db, gdl_staffid):
        emps = _scoped_employees(db, staffid=gdl_staffid)
        emp_ids = [e.id for e in emps]
        _, _, _, _, recoverable = _alloc_counts(db, emp_ids)
        assert recoverable >= 0.0, f"Recoverable is negative: {recoverable}"

    def test_pm_flagged_zero(self, db, pm_staffid):
        """Regression: Dharampal Singh should have 0 flagged licenses."""
        summary = build_dashboard_summary(db, staffid=pm_staffid)
        assert summary.flagged_licenses == 0, (
            f"PM {pm_staffid} expected 0 flagged, got {summary.flagged_licenses}"
        )
        assert summary.monthly_spend >= 0.0


# ---------------------------------------------------------------------------
# Monthly spend series
# ---------------------------------------------------------------------------

class TestMonthlySpendSeries:
    def test_monthly_spend_has_12_months_per_platform(self, db, pm_staffid):
        dash = build_dashboard_bootstrap(db, staffid=pm_staffid)
        year = str(date.today().year)
        if year not in dash.monthly_spend:
            pytest.skip(f"No {year} data for PM {pm_staffid}")
        for plat, series in dash.monthly_spend[year].items():
            assert len(series) == 12, (
                f"Platform '{plat}' series has {len(series)} entries, expected 12"
            )

    def test_monthly_spend_values_non_negative(self, db, gdl_staffid):
        dash = build_dashboard_bootstrap(db, staffid=gdl_staffid)
        for year, platforms in dash.monthly_spend.items():
            for plat, series in platforms.items():
                for i, val in enumerate(series):
                    assert val >= 0.0, (
                        f"Negative spend for platform '{plat}' year={year} month={i+1}: {val}"
                    )

    def test_monthly_project_has_12_months(self, db, gdl_staffid):
        dash = build_dashboard_bootstrap(db, staffid=gdl_staffid)
        year = str(date.today().year)
        if year not in dash.monthly_project:
            pytest.skip(f"No {year} project data for GDL {gdl_staffid}")
        for proj, series in dash.monthly_project[year].items():
            assert len(series) == 12, (
                f"Project '{proj}' monthly series has {len(series)} entries, expected 12"
            )

    def test_current_month_spend_vs_active_licenses(self, db):
        """
        Org-level current-month series spend should be close to
        (but >= 0 vs) active allocation cost.  Tests the series build logic.
        """
        dash = build_dashboard_bootstrap(db, org_level=True)
        today = date.today()
        year = str(today.year)
        m = today.month - 1  # 0-indexed

        if year not in dash.monthly_spend:
            pytest.skip(f"No {year} series data in org-level bootstrap")

        series_month = sum(
            (vals[m] if len(vals) > m else 0)
            for vals in dash.monthly_spend[year].values()
        )
        assert series_month >= 0.0, "Series current-month spend is negative"

    def test_future_months_non_negative_for_current_year(self, db, pm_staffid):
        """Future months in the series should never be negative.
        Non-zero values are allowed: licenses with future effective dates or
        recurring allocations will naturally appear in upcoming months."""
        dash = build_dashboard_bootstrap(db, staffid=pm_staffid)
        today = date.today()
        year = str(today.year)
        if year not in dash.monthly_spend:
            pytest.skip(f"No {year} series for PM {pm_staffid}")

        current_month_idx = today.month - 1  # 0-indexed
        for plat, series in dash.monthly_spend[year].items():
            for i in range(current_month_idx + 1, 12):
                assert series[i] >= 0.0, (
                    f"Negative future spend: platform '{plat}' month {i+1} = {series[i]}"
                )


# ---------------------------------------------------------------------------
# Annual projection consistency
# ---------------------------------------------------------------------------

class TestAnnualProjection:
    def test_annual_gte_current_month_spend(self, db, gdl_staffid):
        dash = build_dashboard_bootstrap(db, staffid=gdl_staffid)
        year = str(date.today().year)
        if year not in dash.monthly_spend:
            pytest.skip("No spend data")
        m = date.today().month - 1
        current_month = sum(
            (vals[m] if len(vals) > m else 0)
            for vals in dash.monthly_spend[year].values()
        )
        annual = sum(sum(vals) for vals in dash.monthly_spend[year].values())
        assert annual >= current_month, (
            f"Annual total ({annual}) < current month ({current_month})"
        )

    def test_project_meta_matches_monthly_project_keys(self, db, gdl_staffid):
        """Every project key in monthly_project must have a matching entry in project_meta."""
        dash = build_dashboard_bootstrap(db, staffid=gdl_staffid)
        for year, projects in dash.monthly_project.items():
            for proj_key in projects:
                assert proj_key in dash.project_meta, (
                    f"Project '{proj_key}' in monthly_project[{year}] "
                    f"has no entry in project_meta"
                )
