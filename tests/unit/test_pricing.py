"""Unit tests for platform and allocation monthly cost resolution."""
from decimal import Decimal
from types import SimpleNamespace

from app.services.pricing import (
    calculate_platform_monthly_unit_cost,
    resolve_allocation_monthly_cost,
)


def _platform(
    *,
    license_type: str = "per_user",
    billing_period: str = "monthly",
    seat_cost=None,
    enterprise_cost=None,
    contracted_seats=None,
    allocation_method: str = "equal",
):
    contract = SimpleNamespace(
        seat_cost=seat_cost,
        enterprise_cost=enterprise_cost,
        contracted_seats=contracted_seats,
        allocation_method=allocation_method,
        effective_from=None,
        id=1,
    )
    return SimpleNamespace(
        license_type=license_type,
        billing_period=billing_period,
        contracts=[contract],
    )


class TestCalculatePlatformMonthlyUnitCost:
    def test_per_user_monthly(self):
        platform = _platform(seat_cost=Decimal("25"))
        assert calculate_platform_monthly_unit_cost(platform) == Decimal("25")

    def test_per_user_annual(self):
        platform = _platform(billing_period="annual", seat_cost=Decimal("65"))
        assert calculate_platform_monthly_unit_cost(platform) == Decimal("5")

    def test_pay_as_you_go_divides_by_pool_seats(self):
        platform = _platform(
            license_type="pay_as_you_go",
            enterprise_cost=Decimal("2000"),
            allocation_method="usage",
        )
        assert calculate_platform_monthly_unit_cost(platform, allocated_seats=4) == Decimal("500")
        assert calculate_platform_monthly_unit_cost(
            platform, allocated_seats=4, pool_seats=154
        ) == Decimal("13")

    def test_empty_license_type_uses_seat_cost(self):
        platform = _platform(
            license_type="",
            seat_cost=Decimal("50"),
            enterprise_cost=Decimal("600"),
        )
        assert calculate_platform_monthly_unit_cost(platform) == Decimal("50")

    def test_enterprise_equal_split(self):
        platform = _platform(
            license_type="enterprise",
            enterprise_cost=Decimal("1200"),
            contracted_seats=10,
            allocation_method="equal",
        )
        assert calculate_platform_monthly_unit_cost(platform, allocated_seats=3) == Decimal("120")

    def test_usage_based_flat_fee_splits_by_active_users(self):
        platform = _platform(
            license_type="usage_based",
            enterprise_cost=Decimal("600"),
            contracted_seats=20,
            allocation_method="equal",
        )
        assert calculate_platform_monthly_unit_cost(platform, allocated_seats=1) == Decimal("600")
        assert calculate_platform_monthly_unit_cost(platform, allocated_seats=3) == Decimal("200")


class TestResolveAllocationMonthlyCost:
    def test_zero_stored_cost_falls_back_to_platform(self):
        platform = _platform(seat_cost=Decimal("25"))
        assert resolve_allocation_monthly_cost(Decimal("0"), platform) == Decimal("25")

    def test_stale_stored_cost_ignored_when_contract_differs(self):
        platform = _platform(seat_cost=Decimal("25"))
        assert resolve_allocation_monthly_cost(Decimal("5.42"), platform) == Decimal("25")

    def test_usage_based_uses_pool_not_zero_snapshot(self):
        platform = _platform(
            license_type="usage_based",
            enterprise_cost=Decimal("600"),
            contracted_seats=20,
        )
        assert resolve_allocation_monthly_cost(
            Decimal("0"), platform, pool_seats=20
        ) == Decimal("30")

    def test_chatgpt_stale_annual_snapshot_uses_monthly_seat(self):
        platform = _platform(
            license_type="per_user",
            billing_period="monthly",
            seat_cost=Decimal("20"),
        )
        assert resolve_allocation_monthly_cost(Decimal("1.67"), platform) == Decimal("20")

    def test_none_stored_cost_uses_platform(self):
        platform = _platform(seat_cost=Decimal("25"))
        assert resolve_allocation_monthly_cost(None, platform) == Decimal("25")
