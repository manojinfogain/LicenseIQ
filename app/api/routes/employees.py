from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.error_utils import handle_database_error, handle_unexpected_error
from app.core.aspire_database import get_aspire_db
from app.models.aspire import AspireEmployee
from app.models.organization import Employee
from app.schemas.employee import EmployeeRead


router = APIRouter()


@router.get("/all")
def list_all_active_employees(
    q: str | None = Query(default=None),
    aspire_db: Session = Depends(get_aspire_db),
) -> list[dict]:
    """Return all active employees from Aspire — used for the raise-request form employee picker."""
    try:
        stmt = select(
            AspireEmployee.emp_staffid,
            AspireEmployee.emp_new_id,
            AspireEmployee.emp_firstname,
            AspireEmployee.emp_lastname,
        ).where(AspireEmployee.emp_isactive == "1")
        if q:
            search = f"%{q}%"
            from sqlalchemy import or_, func
            full_name_expr = func.concat(
                AspireEmployee.emp_firstname, " ", AspireEmployee.emp_lastname
            )
            stmt = stmt.where(
                or_(
                    full_name_expr.ilike(search),
                    AspireEmployee.emp_staffid.ilike(search),
                )
            )
        rows = aspire_db.execute(stmt.order_by(AspireEmployee.emp_firstname, AspireEmployee.emp_lastname)).all()
        return [
            {
                # Use Aspire staff id for requests; backend resolves to local employees.id
                "id": (r.emp_staffid or "").strip(),
                "employee_code": (r.emp_staffid or "").strip(),
                "emp_new_id": (r.emp_new_id or "").strip(),
                "full_name": " ".join(p for p in [r.emp_firstname, r.emp_lastname] if p),
                "employment_status": "active",
            }
            for r in rows
        ]
    except SQLAlchemyError as exc:
        handle_database_error(aspire_db, exc, "list all active employees")
    except Exception as exc:
        handle_unexpected_error(aspire_db, exc, "list all active employees")


@router.get("", response_model=list[EmployeeRead])
def list_employees(
    q: str | None = Query(default=None),
    project_id: int | None = Query(default=None),
    account_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[EmployeeRead]:
    try:
        stmt = select(Employee)
        if q:
            search = f"%{q}%"
            stmt = stmt.where((Employee.full_name.ilike(search)) | (Employee.employee_code.ilike(search)))
        if project_id:
            stmt = stmt.where(Employee.project_id == project_id)
        if account_id:
            stmt = stmt.where(Employee.account_id == account_id)
        return list(db.scalars(stmt.order_by(Employee.full_name)).all())
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "list employees")
    except Exception as exc:
        handle_unexpected_error(db, exc, "list employees")
