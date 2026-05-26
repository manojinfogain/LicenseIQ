from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Aspire EMP_STAFFID that links this user to the Aspire database (e.g. '107348')
    aspire_staff_id: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)

    role_assignments: Mapped[list["UserRoleAssignment"]] = relationship(back_populates="user")


class EmployeeWiseRoleMapping(Base):
    """Maps Aspire EMP_STAFFID to roles (like PlanningMonitoring.dbo.EmployeeWiseRoleMapping)"""
    __tablename__ = "employee_wise_role_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    emp_staffid: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # Aspire ERM_EMPLOYEE_MASTER.EMP_STAFFID
    emp_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), index=True)
    scope_ref_id: Mapped[int | None] = mapped_column(nullable=True)  # Account ID, Project ID, etc if role needs scope
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"), index=True)
    added_on: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=text("GETDATE()"))
    added_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    modified_on: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=text("GETDATE()"))
    modified_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    role: Mapped[Role] = relationship()


class UserRoleAssignment(Base):
    """DEPRECATED: Use EmployeeWiseRoleMapping instead. Kept for backward compatibility."""
    __tablename__ = "user_role_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), index=True)
    user_name: Mapped[str] = mapped_column(String(150))
    role_name: Mapped[str] = mapped_column(String(100))
    scope_type: Mapped[str] = mapped_column(String(50))
    scope_ref_id: Mapped[int | None] = mapped_column(nullable=True)

    user: Mapped[User] = relationship(back_populates="role_assignments")
    role: Mapped[Role] = relationship()
