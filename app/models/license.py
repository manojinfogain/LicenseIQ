from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LicenseAllocation(Base):
    __tablename__ = "license_allocations"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(index=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), index=True)
    project_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    account_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    revoked_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    monthly_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), default="manual")


class AllocationAudit(Base):
    __tablename__ = "allocation_audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    allocation_id: Mapped[int] = mapped_column(ForeignKey("license_allocations.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    event_source: Mapped[str] = mapped_column(String(50))
    old_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    changed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    platform_id: Mapped[int | None] = mapped_column(ForeignKey("platforms.id"), nullable=True, index=True)
    alert_type: Mapped[str] = mapped_column(String(50), index=True)
    priority: Mapped[str] = mapped_column(String(20), index=True)
    source_system: Mapped[str] = mapped_column(String(50), default="manual")
    reason: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LicenseRequest(Base):
    __tablename__ = "license_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_type: Mapped[str] = mapped_column(String(20))
    employee_id: Mapped[int] = mapped_column(index=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), index=True)
    project_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    account_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    requested_by_staffid: Mapped[str | None] = mapped_column(String(20), nullable=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(30), default="submitted")
    # Approval flow tracking: current stage of approval
    approval_stage: Mapped[str] = mapped_column(String(50), default="pending_account_owner", index=True)  # pending_account_owner, pending_it_admin, approved, rejected
    last_approver_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    last_approval_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approval_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ApprovalHistory(Base):
    __tablename__ = "approval_histories"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("license_requests.id"), index=True)
    approval_stage: Mapped[str] = mapped_column(String(50))  # pending_account_owner, pending_it_admin, approved, rejected
    approver_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approver_role: Mapped[str] = mapped_column(String(50))  # account_owner, it_admin, etc.
    action: Mapped[str] = mapped_column(String(20))  # approved, rejected
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QueueItem(Base):
    __tablename__ = "queue_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(30))
    source_id: Mapped[int | None] = mapped_column(nullable=True)
    employee_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    platform_id: Mapped[int | None] = mapped_column(ForeignKey("platforms.id"), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(20))
    project_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    cost_snapshot_monthly: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_to_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    # Approval stage tracking
    approval_stage: Mapped[str] = mapped_column(String(50), nullable=True)  # pending_account_owner, pending_it_admin, etc.
    assigned_approval_role: Mapped[str] = mapped_column(String(50), nullable=True)  # account_owner, it_admin, etc.
    executed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    execution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)



class MonthlySpendFact(Base):
    __tablename__ = "monthly_spend_facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    spend_year: Mapped[int] = mapped_column(index=True)
    spend_month: Mapped[int] = mapped_column(index=True)
    platform_id: Mapped[int | None] = mapped_column(ForeignKey("platforms.id"), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
