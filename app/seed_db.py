"""Populate LicenseIQ database with mock data from the HTML prototype."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine, Base
from app.models.access import User, Role, UserRoleAssignment
from app.models.organization import Account, GDL, Project, Employee
from app.models.platform import Platform, PlatformContract, PlatformSeatSnapshot
from app.models.license import LicenseAllocation, Alert, AllocationAudit


def seed_roles(db: Session) -> None:
    """Create core roles."""
    roles = [
        Role(code="admin", name="License Admin"),
        Role(code="gdl", name="GDL"),
        Role(code="account", name="Account Owner"),
        Role(code="pm", name="Project Manager"),
        Role(code="finance", name="Finance / CFO"),
    ]
    for role in roles:
        db.add(role)
    db.commit()


def seed_users(db: Session) -> None:
    """Create users with role assignments."""
    users_data = [
        ("admin_user", "License Admin", "admin@licenseiq.dev", "admin"),
        ("rajan_mehta", "Rajan Mehta", "rajan@licenseiq.dev", "gdl"),
        ("sunita_rao", "Sunita Rao", "sunita@licenseiq.dev", "account"),
        ("vikram_joshi", "Vikram Joshi", "vikram@licenseiq.dev", "pm"),
        ("preethi_das", "Preethi Das", "preethi@licenseiq.dev", "finance"),
        ("ravi_kumar", "Ravi Kumar", "ravi@licenseiq.dev", "account"),
        ("meena_rao", "Meena Rao", "meena@licenseiq.dev", "account"),
        ("anil_sharma", "Anil Sharma", "anil@licenseiq.dev", "account"),
    ]
    
    for username, full_name, email, role_code in users_data:
        user = User(username=username, full_name=full_name, email=email, is_active=True)
        db.add(user)
        db.flush()  # Flush to get the ID without committing
        
        role = db.query(Role).filter(Role.code == role_code).first()
        if role:
            assignment = UserRoleAssignment(
                user_id=user.id, 
                role_id=role.id, 
                user_name=user.full_name,
                role_name=role.name,
                scope_type="global"
            )
            db.add(assignment)
    db.commit()


def seed_gdls(db: Session) -> None:
    """Create GDL organizations."""
    gdls = [
        GDL(code="GDL-01", display_name="GDL-Delivery-01"),
        GDL(code="GDL-02", display_name="GDL-Delivery-02"),
    ]
    for gdl in gdls:
        db.add(gdl)
    db.commit()


def seed_accounts(db: Session) -> None:
    """Create customer accounts with owner assignments."""
    # Map account names to owner user full names
    account_owners_map = {
        "Alpha Corp": "Sunita Rao",
        "Beta Solutions": "Ravi Kumar",
        "Gamma Ltd": "Meena Rao",
        "Delta Inc": "Anil Sharma",
    }
    
    for acct_name, owner_name in account_owners_map.items():
        owner_user = db.query(User).filter(User.full_name == owner_name).first()
        account = Account(
            name=acct_name,
            status="active",
            owner_user_id=owner_user.id if owner_user else None
        )
        db.add(account)
    db.commit()


def seed_projects(db: Session) -> None:
    """Create projects linked to accounts and GDLs."""
    projects_data = [
        ("Proj-Falcon", "Alpha Corp", "GDL-01"),
        ("Proj-Atlas", "Beta Solutions", "GDL-01"),
        ("Proj-Storm", "Gamma Ltd", "GDL-02"),
        ("Proj-Apex", "Delta Inc", "GDL-02"),
    ]
    
    for proj_name, acct_name, gdl_code in projects_data:
        acct = db.query(Account).filter(Account.name == acct_name).first()
        gdl = db.query(GDL).filter(GDL.code == gdl_code).first()
        
        if acct and gdl:
            proj = Project(name=proj_name, account_id=acct.id, gdl_id=gdl.id, status="active")
            db.add(proj)
    db.commit()


def seed_platforms(db: Session) -> None:
    """Create software platforms and their contracts."""
    platforms_data = [
        {
            "name": "GitHub",
            "vendor": "Microsoft",
            "cat": "Dev tools",
            "agr": "standard",
            "type": "per_user",
            "billing": "monthly",
            "currency": "USD",
            "inactiveDays": 30,
            "effective": "2024-01-01",
            "renewal": "2025-03-31",
            "seat_cost": 21,
            "contracted_seats": 100,
        },
        {
            "name": "Docker",
            "vendor": "Docker Inc.",
            "cat": "Infrastructure",
            "agr": "enterprise",
            "type": "enterprise",
            "billing": "annual",
            "currency": "USD",
            "inactiveDays": 30,
            "effective": "2024-01-15",
            "renewal": "2025-01-15",
            "ent_cost": 5760,
            "contracted_seats": 100,
        },
        {
            "name": "Visual Studio",
            "vendor": "Microsoft",
            "cat": "IDE",
            "agr": "enterprise",
            "type": "enterprise",
            "billing": "annual",
            "currency": "USD",
            "inactiveDays": 30,
            "effective": "2024-04-01",
            "renewal": "2025-04-23",
            "ent_cost": 54720,
            "contracted_seats": 120,
        },
        {
            "name": "OpenAI Teams",
            "vendor": "OpenAI",
            "cat": "AI / ML",
            "agr": "standard",
            "type": "per_user",
            "billing": "monthly",
            "currency": "USD",
            "inactiveDays": 30,
            "effective": "2024-01-01",
            "renewal": "2025-06-30",
            "seat_cost": 25,
            "contracted_seats": 60,
        },
        {
            "name": "Cursor",
            "vendor": "Anysphere",
            "cat": "IDE",
            "agr": "standard",
            "type": "per_user",
            "billing": "monthly",
            "currency": "USD",
            "inactiveDays": 30,
            "effective": "2024-01-01",
            "renewal": "2025-12-31",
            "seat_cost": 20,
            "contracted_seats": 30,
        },
    ]
    
    for data in platforms_data:
        platform = Platform(
            name=data["name"],
            vendor=data["vendor"],
            category=data["cat"],
            agreement_type=data["agr"],
            license_type=data["type"],
            billing_period=data["billing"],
            currency=data["currency"],
            inactivity_days=data["inactiveDays"],
            contractor_allowed=True,
            shared_allowed=False,
            api_available=(data["name"] == "Docker"),
            effective_date=date.fromisoformat(data["effective"]),
            renewal_date=date.fromisoformat(data["renewal"]),
            is_active=True,
        )
        db.add(platform)
        db.flush()
        
        contract = PlatformContract(
            platform_id=platform.id,
            cost_model=data["type"],
            seat_cost=Decimal(str(data.get("seat_cost", 0))),
            enterprise_cost=Decimal(str(data.get("ent_cost", 0))),
            contracted_seats=data.get("contracted_seats"),
            allocation_method="equal" if data["type"] == "per_user" else ("equal" if "Visual" in data["name"] else "usage"),
            effective_from=date.fromisoformat(data["effective"]),
            effective_to=date.fromisoformat(data["renewal"]),
        )
        db.add(contract)
    
    db.commit()


def seed_seat_snapshots(db: Session) -> None:
    """Create platform seat count snapshots."""
    snapshots_data = {
        "GitHub": [(date(2024, 1, 1), 75), (date(2024, 3, 1), 80), (date(2024, 6, 1), 82)],
        "Docker": [(date(2024, 1, 1), 55), (date(2024, 4, 1), 60), (date(2024, 7, 1), 61)],
        "Visual Studio": [(date(2024, 1, 1), 90), (date(2024, 4, 1), 95)],
        "OpenAI Teams": [(date(2024, 1, 1), 44), (date(2024, 3, 1), 48)],
        "Cursor": [(date(2024, 1, 1), 18), (date(2024, 5, 1), 20)],
    }
    
    for plat_name, snapshots in snapshots_data.items():
        platform = db.query(Platform).filter(Platform.name == plat_name).first()
        if platform:
            for snap_date, seat_count in snapshots:
                snap = PlatformSeatSnapshot(
                    platform_id=platform.id,
                    snapshot_date=snap_date,
                    seat_count=seat_count,
                )
                db.add(snap)
    db.commit()


def seed_employees(db: Session) -> None:
    """Create employees and their allocations with account owner assignments."""
    employees_data = [
        ("EMP-001", "Arjun Mehta", "Engineering", "Proj-Falcon", "Alpha Corp", "Sunita Rao", "GDL-01", "active"),
        ("EMP-002", "Priya Sharma", "Delivery", "Proj-Atlas", "Beta Solutions", "Ravi Kumar", "GDL-01", "active"),
        ("EMP-003", "Rahul Verma", "Engineering", "Proj-Falcon", "Alpha Corp", "Sunita Rao", "GDL-01", "active"),
        ("EMP-004", "Sneha Nair", "Studio", "Proj-Storm", "Gamma Ltd", "Meena Rao", "GDL-02", "active"),
        ("EMP-005", "Kiran Rao", "Engineering", "Proj-Apex", "Delta Inc", "Anil Sharma", "GDL-02", "active"),
        ("EMP-006", "Deepa Singh", "Support", "Proj-Atlas", "Beta Solutions", "Ravi Kumar", "GDL-01", "exited"),
        ("EMP-007", "Vikram Joshi", "Sales", "Proj-Falcon", "Alpha Corp", "Sunita Rao", "GDL-01", "active"),
        ("EMP-008", "Ananya Pillai", "Delivery", "Proj-Storm", "Gamma Ltd", "Meena Rao", "GDL-02", "active"),
        ("EMP-009", "Meera Iyer", "Engineering", "Proj-Apex", "Delta Inc", "Anil Sharma", "GDL-02", "bench"),
        ("EMP-010", "Raj Pillai", "Support", "Proj-Atlas", "Beta Solutions", "Ravi Kumar", "GDL-01", "active"),
        ("EMP-011", "Neha Gupta", "Sales", "Proj-Storm", "Gamma Ltd", "Meena Rao", "GDL-02", "active"),
        ("EMP-012", "Sanjay Rao", "Studio", "Proj-Apex", "Delta Inc", "Anil Sharma", "GDL-02", "active"),
    ]
    
    for emp_id, name, unit, proj_name, acct_name, acct_owner, gdl_code, status in employees_data:
        proj = db.query(Project).filter(Project.name == proj_name).first()
        acct = db.query(Account).filter(Account.name == acct_name).first()
        gdl = db.query(GDL).filter(GDL.code == gdl_code).first()
        owner_user = db.query(User).filter(User.full_name == acct_owner).first()
        
        if proj and acct and gdl:
            emp = Employee(
                employee_code=emp_id,
                full_name=name,
                unit=unit,
                employment_status=status,
                account_id=acct.id,
                project_id=proj.id,
                gdl_id=gdl.id,
                account_owner_user_id=owner_user.id if owner_user else None,
            )
            db.add(emp)
    db.commit()


def seed_allocations(db: Session) -> None:
    """Create license allocations based on EMPS data from HTML."""
    allocations_data = [
        ("EMP-001", "GitHub", "Proj-Falcon", "Alpha Corp", "active", date(2024, 1, 10), Decimal("21")),
        ("EMP-001", "Cursor", "Proj-Falcon", "Alpha Corp", "active", date(2024, 2, 15), Decimal("20")),
        ("EMP-002", "OpenAI Teams", "Proj-Atlas", "Beta Solutions", "inactive", date(2024, 1, 5), Decimal("25")),
        ("EMP-003", "Docker", "Proj-Falcon", "Alpha Corp", "flagged", date(2024, 1, 15), Decimal("48")),
        ("EMP-003", "GitHub", "Proj-Falcon", "Alpha Corp", "active", date(2024, 1, 10), Decimal("21")),
        ("EMP-004", "Visual Studio", "Proj-Storm", "Gamma Ltd", "active", date(2024, 4, 1), Decimal("38")),
        ("EMP-004", "GitHub", "Proj-Storm", "Gamma Ltd", "active", date(2024, 4, 1), Decimal("21")),
        ("EMP-005", "Cursor", "Proj-Apex", "Delta Inc", "active", date(2024, 1, 1), Decimal("20")),
        ("EMP-005", "Visual Studio", "Proj-Apex", "Delta Inc", "active", date(2024, 1, 1), Decimal("38")),
        ("EMP-006", "GitHub", "Proj-Atlas", "Beta Solutions", "active", date(2023, 11, 1), Decimal("21")),
        ("EMP-006", "Cursor", "Proj-Atlas", "Beta Solutions", "active", date(2024, 1, 10), Decimal("20")),
        ("EMP-007", "OpenAI Teams", "Proj-Falcon", "Alpha Corp", "active", date(2024, 1, 1), Decimal("25")),
        ("EMP-008", "Docker", "Proj-Storm", "Gamma Ltd", "flagged", date(2024, 1, 15), Decimal("48")),
        ("EMP-008", "OpenAI Teams", "Proj-Storm", "Gamma Ltd", "inactive", date(2024, 2, 10), Decimal("25")),
        ("EMP-009", "GitHub", "Proj-Apex", "Delta Inc", "active", date(2023, 10, 1), Decimal("21")),
        ("EMP-009", "Visual Studio", "Proj-Apex", "Delta Inc", "active", date(2023, 12, 1), Decimal("38")),
        ("EMP-009", "Docker", "Proj-Apex", "Delta Inc", "active", date(2024, 1, 15), Decimal("48")),
        ("EMP-010", "Visual Studio", "Proj-Atlas", "Beta Solutions", "active", date(2024, 4, 1), Decimal("38")),
        ("EMP-010", "Cursor", "Proj-Atlas", "Beta Solutions", "active", date(2024, 4, 1), Decimal("20")),
        ("EMP-011", "OpenAI Teams", "Proj-Storm", "Gamma Ltd", "active", date(2024, 4, 2), Decimal("25")),
        ("EMP-011", "GitHub", "Proj-Storm", "Gamma Ltd", "active", date(2024, 4, 2), Decimal("21")),
        ("EMP-012", "Cursor", "Proj-Apex", "Delta Inc", "active", date(2024, 1, 1), Decimal("20")),
    ]
    
    for emp_id, plat_name, proj_name, acct_name, status, eff_date, cost in allocations_data:
        emp = db.query(Employee).filter(Employee.employee_code == emp_id).first()
        plat = db.query(Platform).filter(Platform.name == plat_name).first()
        proj = db.query(Project).filter(Project.name == proj_name).first()
        acct = db.query(Account).filter(Account.name == acct_name).first()
        
        if emp and plat and proj and acct:
            alloc = LicenseAllocation(
                employee_id=emp.id,
                platform_id=plat.id,
                project_id=proj.id,
                account_id=acct.id,
                status=status,
                effective_date=eff_date,
                monthly_cost=cost,
                source_type="manual",
            )
            db.add(alloc)
    
    db.commit()


def seed_alerts(db: Session) -> None:
    """Create sample alerts."""
    alerts_data = [
        ("EMP-006", None, "exit", "high", "Exit event from Aspire — 31 Mar 2024", "All licenses must be revoked immediately."),
        ("EMP-009", None, "bench", "high", "Bench event from Aspire — 28 Mar 2024", "Employee unbillable. All licenses should be revoked."),
        ("EMP-003", None, "project", "medium", "Project change from Aspire — 15 Mar 2024", "Docker still billed to old project. Cost reallocation required."),
        ("EMP-002", None, "revoke", "medium", "Inactivity flag — no login 60+ days", "No activity since 15 Jan."),
        ("EMP-008", None, "revoke", "medium", "Inactivity flag — multiple platforms 45+ days", "Docker and OpenAI Teams both unused."),
        ("EMP-001", None, "revoke", "low", "Inactivity flag — Cursor unused 30 days", "Low priority. Confirm if still needed."),
    ]
    
    for emp_id, plat_id, alert_type, priority, reason, detail in alerts_data:
        emp = db.query(Employee).filter(Employee.employee_code == emp_id).first()
        if emp:
            alert = Alert(
                employee_id=emp.id,
                platform_id=plat_id,
                alert_type=alert_type,
                priority=priority,
                source_system="aspire",
                reason=reason,
                detail=detail,
                status="open",
            )
            db.add(alert)
    
    db.commit()


def main() -> None:
    """Run all seed operations."""
    db = SessionLocal()
    try:
        # Clear all tables
        print("Clearing existing data...")
        from sqlalchemy import text
        
        # Disable all foreign key checks
        db.execute(text("EXEC sp_MSForEachTable 'ALTER TABLE ? NOCHECK CONSTRAINT ALL'"))
        db.commit()
        
        # Delete all data from tables that exist
        tables_to_clear = [
            "allocation_audits",
            "license_allocations",
            "alerts",
            "license_requests",  # Fixed: was "requests", likely renamed
            "queue_items",
            "monthly_spend_facts",
            "platform_seat_snapshots",
            "platform_contracts",
            "platforms",
            "employees",
            "projects",
            "accounts",
            "gdls",
            "user_role_assignments",
            "users",
            "roles",
        ]
        
        for table in tables_to_clear:
            try:
                db.execute(text(f"DELETE FROM {table}"))
            except:
                pass  # Table might not exist
        
        db.commit()
        
        # Re-enable all foreign key checks
        db.execute(text("EXEC sp_MSForEachTable 'ALTER TABLE ? CHECK CONSTRAINT ALL'"))
        db.commit()
        
        print("Seeding roles...")
        seed_roles(db)
        print("Seeding users...")
        seed_users(db)
        print("Seeding GDLs...")
        seed_gdls(db)
        print("Seeding accounts...")
        seed_accounts(db)
        print("Seeding projects...")
        seed_projects(db)
        print("Seeding platforms...")
        seed_platforms(db)
        print("Seeding seat snapshots...")
        seed_seat_snapshots(db)
        print("Seeding employees...")
        seed_employees(db)
        print("Seeding allocations...")
        seed_allocations(db)
        print("Seeding alerts...")
        seed_alerts(db)
        print("Database seeding complete!")
    finally:
        db.close()


if __name__ == "__main__":
    main()
