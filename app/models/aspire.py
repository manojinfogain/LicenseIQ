"""
SQLAlchemy ORM models for Aspire database.
IMPORTANT: These are READ-ONLY mappings to Aspire tables.
Do NOT modify these tables - only query data from them.
"""

from datetime import datetime
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.aspire_database import AspireBase as Base


class AspireEmployee(Base):
    """Maps to ASPIRE.DBO.ERM_EMPLOYEE_MASTER"""
    __tablename__ = "ERM_EMPLOYEE_MASTER"
    __table_args__ = {"schema": "DBO"}

    emp_staffid: Mapped[str] = mapped_column("EMP_STAFFID", String(20), primary_key=True)
    emp_new_id: Mapped[str | None] = mapped_column("Emp_NewID", String(50), nullable=True)
    emp_firstname: Mapped[str | None] = mapped_column("EMP_FIRSTNAME", String(100), nullable=True)
    emp_lastname: Mapped[str | None] = mapped_column("EMP_LASTNAME", String(100), nullable=True)
    emp_middlename: Mapped[str | None] = mapped_column("EMP_MIDDLENAME", String(100), nullable=True)
    emp_mailid: Mapped[str | None] = mapped_column("EMP_MAILID", String(255), nullable=True)
    emp_isactive: Mapped[str | None] = mapped_column("EMP_ISACTIVE", String(1), nullable=True)  # '1' active, '0' inactive
    emp_status: Mapped[str | None] = mapped_column("EMP_STATUS", String(1), nullable=True)
    emp_dateofjoining: Mapped[datetime | None] = mapped_column("EMP_DATEOFJOINING", nullable=True)
    emp_designation_code: Mapped[int | None] = mapped_column("EMP_DESIGNATION_CODE", Integer, nullable=True)

    # Relationships
    project_assignments: Mapped[list["AspireProjectAssignment"]] = relationship(
        back_populates="employee", foreign_keys="AspireProjectAssignment.asg_emp_staffid"
    )

    @property
    def full_name(self) -> str:
        """Concatenate first and last name only"""
        parts = [self.emp_firstname or "", self.emp_lastname or ""]
        return " ".join(p.strip() for p in parts if p.strip())

    @property
    def email(self) -> str:
        return self.emp_mailid or ""

    @property
    def is_active(self) -> bool:
        return (self.emp_isactive or "").strip() == "1"


class AspireProject(Base):
    """Maps to ASPIRE.DBO.RPT_PROJECT_MASTER"""
    __tablename__ = "RPT_PROJECT_MASTER"
    __table_args__ = {"schema": "DBO"}

    project_id: Mapped[int] = mapped_column("PROJECT_ID", Integer, primary_key=True)
    project_name: Mapped[str | None] = mapped_column("PROJECT_NAME", String(255), nullable=True)
    account_id: Mapped[int | None] = mapped_column("ACCOUNT_ID", ForeignKey("DBO.RPT_ACCOUNT_MASTER.ACCOUNT_ID"), nullable=True)
    deliveryunit_id: Mapped[int | None] = mapped_column(
        "DeliveryUnitId", ForeignKey("DBO.RPT_DELIVERYUNIT_MASTER.DeliveryUnitID"), nullable=True
    )
    projectmngr_id: Mapped[str | None] = mapped_column("PROJECTMNGR_ID", String(20), nullable=True)
    onsite_pm: Mapped[str | None] = mapped_column("OnsitePM", String(20), nullable=True)
    offshore_pm: Mapped[str | None] = mapped_column("OffShorePM", String(20), nullable=True)
    project_status: Mapped[str | None] = mapped_column("PROJECT_STATUS", String(1), nullable=True)
    oracle_project_id: Mapped[str | None] = mapped_column("OracleProjectId", String(100), nullable=True)
    prj_startdate: Mapped[datetime | None] = mapped_column("PRJ_STARTDATE", nullable=True)
    prj_enddate: Mapped[datetime | None] = mapped_column("PRJ_ENDDATE", nullable=True)

    # Relationships
    account: Mapped["AspireAccount"] = relationship(foreign_keys=[account_id])
    delivery_unit: Mapped["AspireDeliveryUnit"] = relationship(foreign_keys=[deliveryunit_id])
    assignments: Mapped[list["AspireProjectAssignment"]] = relationship(
        back_populates="project", foreign_keys="AspireProjectAssignment.asg_project_id"
    )

    @property
    def is_active(self) -> bool:
        return self.project_status in ("A", "O")


class AspireProjectAssignment(Base):
    """Maps to ASPIRE.DBO.RPT_PROJECT_ASSIGNMENT"""
    __tablename__ = "RPT_PROJECT_ASSIGNMENT"
    __table_args__ = {"schema": "DBO"}

    id: Mapped[int] = mapped_column("Id", Integer, primary_key=True)
    asg_emp_staffid: Mapped[str] = mapped_column(
        "ASG_EMP_STAFFID", String(20), ForeignKey("DBO.ERM_EMPLOYEE_MASTER.EMP_STAFFID"), index=True
    )
    asg_project_id: Mapped[int] = mapped_column(
        "ASG_PROJECT_ID", Integer, ForeignKey("DBO.RPT_PROJECT_MASTER.PROJECT_ID"), index=True
    )
    project_startdate: Mapped[datetime | None] = mapped_column("PROJECT_STARTDATE", nullable=True)
    project_enddate: Mapped[datetime | None] = mapped_column("PROJECT_ENDDATE", nullable=True)
    billable: Mapped[str | None] = mapped_column("BILLABLE", String(1), nullable=True)
    asg_role_id: Mapped[int | None] = mapped_column("ASG_ROLE_ID", Integer, nullable=True)

    # Relationships
    employee: Mapped[AspireEmployee] = relationship(back_populates="project_assignments")
    project: Mapped[AspireProject] = relationship(back_populates="assignments")


class AspireAccount(Base):
    """Maps to ASPIRE.DBO.RPT_ACCOUNT_MASTER"""
    __tablename__ = "RPT_ACCOUNT_MASTER"
    __table_args__ = {"schema": "DBO"}

    account_id: Mapped[int] = mapped_column("ACCOUNT_ID", Integer, primary_key=True)
    account_name: Mapped[str | None] = mapped_column("ACCOUNT_NAME", String(255), nullable=True)
    account_owner: Mapped[str | None] = mapped_column("ACCOUNT_OWNER", String(20), nullable=True)
    account_status: Mapped[str | None] = mapped_column("ACCOUNT_STATUS", String(1), nullable=True)
    bu_id: Mapped[int | None] = mapped_column("BU_ID", Integer, nullable=True)

    # Relationships
    projects: Mapped[list[AspireProject]] = relationship(foreign_keys="AspireProject.account_id", overlaps="account")

    @property
    def is_active(self) -> bool:
        return self.account_status == "A"


class AspireDeliveryUnit(Base):
    """Maps to ASPIRE.DBO.RPT_DELIVERYUNIT_MASTER"""
    __tablename__ = "RPT_DELIVERYUNIT_MASTER"
    __table_args__ = {"schema": "DBO"}

    deliveryunit_id: Mapped[int] = mapped_column("DeliveryUnitID", Integer, primary_key=True)
    deliveryunit: Mapped[str | None] = mapped_column("DeliveryUnit", String(255), nullable=True)
    deliveryhead: Mapped[str | None] = mapped_column("DeliveryHead", String(20), nullable=True)
    status: Mapped[str | None] = mapped_column("Status", String(1), nullable=True)
    type: Mapped[str | None] = mapped_column("Type", String(50), nullable=True)

    # Relationships
    projects: Mapped[list[AspireProject]] = relationship(foreign_keys="AspireProject.deliveryunit_id", overlaps="delivery_unit")

    @property
    def code(self) -> str:
        """Alias for deliveryunit (for compatibility)"""
        return self.deliveryunit or ""

    @property
    def display_name(self) -> str:
        """Alias for deliveryunit (for compatibility)"""
        return self.deliveryunit or ""

    @property
    def is_active(self) -> bool:
        return self.status == "A"


class AspireResignation(Base):
    """Maps to ASPIRE.DBO.SEP_ResignationDetails — primary exit/resignation table."""
    __tablename__ = "SEP_ResignationDetails"
    __table_args__ = {"schema": "DBO"}

    id: Mapped[int] = mapped_column("Id", Integer, primary_key=True)
    emp_id: Mapped[str | None] = mapped_column("EmpId", String(20), index=True, nullable=True)
    resignation_date: Mapped[datetime | None] = mapped_column("ResignationDate", nullable=True)
    last_working_date: Mapped[datetime | None] = mapped_column("LastWorkingDate", nullable=True)
    resignation_reason: Mapped[str | None] = mapped_column("ResignationReason", String(1000), nullable=True)
    resigned_status: Mapped[str | None] = mapped_column("ResignedStatus", String(1), nullable=True)
    exit_type: Mapped[str | None] = mapped_column("ExitType", String(2), nullable=True)
    project: Mapped[str | None] = mapped_column("Project", String(255), nullable=True)
    account: Mapped[str | None] = mapped_column("Account", String(255), nullable=True)
    is_active: Mapped[bool | None] = mapped_column("IsActive", nullable=True)
    is_deleted: Mapped[bool | None] = mapped_column("IsDeleted", nullable=True)
    added_on: Mapped[datetime | None] = mapped_column("AddedOn", nullable=True)
    modified_on: Mapped[datetime | None] = mapped_column("ModifiedOn", nullable=True)
    revert_date: Mapped[datetime | None] = mapped_column("ResignationRevertDate", nullable=True)


class AspireProjectRelease(Base):
    """Maps to ASPIRE.DBO.RPT_FeedbackOnRelease — employee release from project."""
    __tablename__ = "RPT_FeedbackOnRelease"
    __table_args__ = {"schema": "DBO"}

    id: Mapped[int] = mapped_column("Id", Integer, primary_key=True)
    employee_id: Mapped[str | None] = mapped_column("EmployeeId", String(100), index=True, nullable=True)
    account_id: Mapped[int | None] = mapped_column("AccountId", Integer, nullable=True)
    project_id: Mapped[int | None] = mapped_column("ProjectId", Integer, nullable=True)
    release_reason: Mapped[int | None] = mapped_column("ReleaseReason", Integer, nullable=True)
    allocation_end_date: Mapped[datetime | None] = mapped_column("AllocationEndDate", nullable=True)
    feedback_given_on: Mapped[datetime | None] = mapped_column("FeedbackGivenOn", nullable=True)
    is_active: Mapped[int | None] = mapped_column("IsActive", Integer, nullable=True)
    allocation_id: Mapped[int | None] = mapped_column("AllocationId", Integer, nullable=True)
