from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.license import LicenseAllocation
from app.models.platform import Platform


def round_monthly_cost(amount: Decimal | float | int) -> Decimal:
    """Round to whole dollars for consistent UI display."""
    return Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def money_float(amount: Decimal | float | int) -> float:
    return float(round_monthly_cost(amount))


def platform_pool_active_seat_count(db: Session, platform_id: int) -> int:
    """Org-wide current allocation count for pool-style pricing (pay-as-you-go, etc.)."""
    return int(
        db.scalar(
            select(func.count(func.distinct(LicenseAllocation.employee_id))).where(
                LicenseAllocation.platform_id == platform_id,
                LicenseAllocation.revoked_date.is_(None),
            )
        )
        or 0
    )


def _latest_contract(platform: Platform):
    if not platform.contracts:
        return None
    return sorted(
        platform.contracts,
        key=lambda item: item.effective_from or item.id,
        reverse=True,
    )[0]


def calculate_platform_monthly_unit_cost(
    platform: Platform,
    allocated_seats: int | None = None,
    pool_seats: int | None = None,
) -> Decimal:
    """Monthly unit cost for one allocation, aligned with Platform master (platUC)."""
    contract = _latest_contract(platform)
    if not contract:
        return Decimal("0")

    license_type = (platform.license_type or "").strip().lower()
    billing = (platform.billing_period or "").strip().lower()
    allocation_method = (contract.allocation_method or "equal").strip().lower()

    if license_type == "usage_based":
        if not contract.enterprise_cost:
            return Decimal("0")
        monthly_total = Decimal(contract.enterprise_cost)
        if billing == "annual":
            monthly_total = monthly_total / Decimal("12")
        # Flat platform fee; per-allocation share uses org-wide pool, not scoped count.
        seats = max(pool_seats or allocated_seats or 1, 1)
        return round_monthly_cost(monthly_total / Decimal(seats))

    if license_type in ("per_user", "perpetual") or (
        contract.seat_cost and license_type not in ("enterprise", "pay_as_you_go", "usage_based")
    ):
        if not contract.seat_cost:
            return Decimal("0")
        seat = Decimal(contract.seat_cost)
        if billing == "annual":
            return round_monthly_cost(seat / Decimal("12"))
        return round_monthly_cost(seat)

    if contract.seat_cost and not contract.enterprise_cost:
        seat = Decimal(contract.seat_cost)
        if billing == "annual":
            return round_monthly_cost(seat / Decimal("12"))
        return round_monthly_cost(seat)

    if not contract.enterprise_cost:
        return Decimal("0")

    monthly_total = Decimal(contract.enterprise_cost)
    if billing == "annual":
        monthly_total = monthly_total / Decimal("12")

    if allocation_method == "equal":
        seats = max(contract.contracted_seats or 1, 1)
    else:
        # Pay-as-you-go / usage-weighted: divide pool by org-wide active seats.
        seats = max(pool_seats or allocated_seats or contract.contracted_seats or 1, 1)
    return round_monthly_cost(monthly_total / Decimal(seats))


def resolve_allocation_monthly_cost(
    monthly_cost: Decimal | float | None,
    platform: Platform | None = None,
    *,
    allocated_seats: int | None = None,
    pool_seats: int | None = None,
) -> Decimal:
    """Derive from platform contract (Platform master); ignore stale allocation snapshots."""
    if platform:
        license_type = (platform.license_type or "").strip().lower()
        contract_cost = calculate_platform_monthly_unit_cost(
            platform,
            allocated_seats,
            pool_seats=pool_seats,
        )
        # Pool / contract pricing matches Platform master (platUC).
        if license_type in ("pay_as_you_go", "usage_based") and pool_seats:
            return contract_cost
        if contract_cost > 0:
            return contract_cost
    if monthly_cost is not None:
        stored = round_monthly_cost(monthly_cost)
        if stored > 0:
            return stored
    if platform:
        return calculate_platform_monthly_unit_cost(
            platform,
            allocated_seats,
            pool_seats=pool_seats,
        )
    return Decimal("0")


def calculate_platform_monthly_unit_cost_for_platform(
    db: Session,
    platform: Platform,
) -> Decimal:
    """Unit cost using org-wide pool size for pay-as-you-go / usage-weighted models."""
    pool = platform_pool_active_seat_count(db, platform.id)
    return calculate_platform_monthly_unit_cost(
        platform,
        pool_seats=pool or None,
    )
