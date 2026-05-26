from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Platform(Base):
    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    vendor: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(100))
    agreement_type: Mapped[str] = mapped_column(String(50))
    license_type: Mapped[str] = mapped_column(String(50))
    billing_period: Mapped[str] = mapped_column(String(30))
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    inactivity_days: Mapped[int] = mapped_column(default=30)
    contractor_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    shared_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    api_available: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    renewal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contracts: Mapped[list["PlatformContract"]] = relationship(back_populates="platform")
    seat_snapshots: Mapped[list["PlatformSeatSnapshot"]] = relationship(back_populates="platform")


class PlatformContract(Base):
    __tablename__ = "platform_contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), index=True)
    cost_model: Mapped[str] = mapped_column(String(50))
    seat_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    enterprise_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    contracted_seats: Mapped[int | None] = mapped_column(nullable=True)
    allocation_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    platform: Mapped[Platform] = relationship(back_populates="contracts")


class PlatformSeatSnapshot(Base):
    __tablename__ = "platform_seat_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date)
    seat_count: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    platform: Mapped[Platform] = relationship(back_populates="seat_snapshots")
