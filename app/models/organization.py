from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")


class GDL(Base):
    __tablename__ = "gdls"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(150))


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    gdl_id: Mapped[int | None] = mapped_column(ForeignKey("gdls.id"), nullable=True)
    project_manager_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")

    account: Mapped[Account] = relationship()
    gdl: Mapped[GDL | None] = relationship()


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150), index=True)
    unit: Mapped[str] = mapped_column(String(100), index=True)
    employment_status: Mapped[str] = mapped_column(String(30), default="active")
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    gdl_id: Mapped[int | None] = mapped_column(ForeignKey("gdls.id"), nullable=True)
    account_owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    account: Mapped[Account] = relationship()
    project: Mapped[Project] = relationship()
    gdl: Mapped[GDL | None] = relationship()
