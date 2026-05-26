from datetime import date
import csv
import io
from typing import Literal
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from openpyxl import Workbook
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.error_utils import handle_database_error, handle_unexpected_error
from app.api.query_helpers import validate_user_exists
from app.services.bulk_import import parse_csv_rows, run_bulk_license_import


router = APIRouter()


TEMPLATE_HEADERS = ["User Name", "Email ID", "Platform", "StaffID", "Emp_newID"]
TEMPLATE_SAMPLE_ROWS = [
    ["Gaurav Karkhanis", "gaurav.karkhanis@infogain.com", "ChatGPT", "118091", "121244"],
    ["Mandar Deshmukh", "mandar.deshmukh@infogain.com", "Claude AI", "40702", "101930"],
]


class BulkImportRowResult(BaseModel):
    row_number: int = Field(description="CSV row number, including the original header row offset.")
    status: str = Field(
        description="Per-row outcome. Values include inserted, would_insert, skipped_duplicate, exception, and failed."
    )
    employee_name: str | None = Field(default=None, description="Employee name as received from the CSV row.")
    staff_id: str | None = Field(default=None, description="StaffID from the CSV row. This is the only identifier used for assignment resolution.")
    emp_new_id: str | None = Field(default=None, description="Emp_newID from the CSV row, returned for diagnostics only.")
    email: str | None = Field(default=None, description="Email ID from the CSV row, returned for diagnostics only.")
    platform_name: str | None = Field(default=None, description="Normalized platform name used for lookup.")
    message: str = Field(description="Detailed row-level result or error message.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "row_number": 2,
                "status": "inserted",
                "employee_name": "Gaurav Karkhanis",
                "staff_id": "1030",
                "emp_new_id": "121244",
                "email": "gaurav.karkhanis@infogain.com",
                "platform_name": "OpenAI Teams",
                "message": "License assigned successfully.",
            }
        }
    }


class BulkImportResponse(BaseModel):
    total_rows: int = Field(description="Total number of data rows parsed from the CSV file.")
    inserted_count: int = Field(description="Rows successfully written to queue_items, license_allocations, and allocation_audits.")
    skipped_duplicate_count: int = Field(description="Rows skipped because an active or pending assignment already exists.")
    exception_count: int = Field(description="Rows rejected due to validation or data resolution issues.")
    failed_count: int = Field(description="Rows that failed during processing after validation started.")
    has_errors: bool = Field(description="True when at least one CSV row has status `exception` or `failed`.")
    error_row_numbers: list[int] = Field(description="List of CSV row numbers that contain errors and require user attention.")
    summary_message: str = Field(description="Top-level summary that highlights whether the uploaded CSV contains any invalid rows.")
    accepted_platform_names: list[str] = Field(description="Exact platform names currently accepted by the application for the `Platform` column.")
    row_results: list[BulkImportRowResult] = Field(description="Detailed result for every processed CSV row.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "total_rows": 4,
                "inserted_count": 3,
                "skipped_duplicate_count": 0,
                "exception_count": 1,
                "failed_count": 0,
                "has_errors": True,
                "error_row_numbers": [5],
                "summary_message": "CSV contains one or more invalid rows. Review row_results and error_row_numbers: [5].",
                "accepted_platform_names": [
                    "ChatGPT",
                    "Claude AI",
                    "Cursor AI",
                    "Docker Hub",
                    "Github Copilot",
                    "Langwatch AI",
                    "Open AI Platform",
                    "PineCone AI"
                ],
                "row_results": [
                    {
                        "row_number": 2,
                        "status": "inserted",
                        "employee_name": "Gaurav Karkhanis",
                        "staff_id": "1030",
                        "emp_new_id": "121244",
                        "email": "gaurav.karkhanis@infogain.com",
                        "platform_name": "ChatGPT",
                        "message": "License assigned successfully.",
                    },
                    {
                        "row_number": 5,
                        "status": "exception",
                        "employee_name": "Pankaj Kumar",
                        "staff_id": None,
                        "emp_new_id": "104411",
                        "email": "pankaj.kumar@infogain.com",
                        "platform_name": "Open AI Platform",
                        "message": "Missing required StaffID. Bulk import resolves employees by StaffID only.",
                    },
                ],
            }
        }
    }


@router.get(
    "/template",
    summary="Download bulk import template",
    description=(
        "Downloads a ready-to-fill bulk import template with the exact headers expected by the upload endpoint. "
        "Use this file, populate rows, and upload it to `/api/v1/bulk-import/licenses`."
    ),
    responses={
        200: {
            "description": "Template file generated successfully.",
            "content": {
                "text/csv": {},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
            },
        },
    },
)
def download_bulk_import_template(
    file_format: Annotated[
        Literal["csv", "xlsx"],
        Query(description="Template format. Use `csv` or `xlsx`.")
    ] = "csv",
) -> Response:
    if file_format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(TEMPLATE_HEADERS)
        writer.writerows(TEMPLATE_SAMPLE_ROWS)
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=bulk_import_template.csv"},
        )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "BulkImportTemplate"
    sheet.append(TEMPLATE_HEADERS)
    for row in TEMPLATE_SAMPLE_ROWS:
        sheet.append(row)

    file_buffer = io.BytesIO()
    workbook.save(file_buffer)
    return Response(
        content=file_buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=bulk_import_template.xlsx"},
    )


@router.post(
    "/licenses",
    response_model=BulkImportResponse,
    summary="Bulk import license assignments from CSV",
    description=(
        "Uploads a CSV file and assigns platform licenses in bulk. "
        "Employees are resolved strictly by the `StaffID` column. "
        "`Email ID` and `Emp_newID` are accepted for diagnostics only and are not used for assignment matching.\n\n"
        "Expected CSV headers:\n"
        "- `User Name`\n"
        "- `Email ID`\n"
        "- `Platform`\n"
        "- `StaffID`\n"
        "- `Emp_newID`\n\n"
        "Exact `Platform` values currently expected in the application master are:\n"
        "- `Github Copilot`\n"
        "- `Open AI Platform`\n"
        "- `Claude AI`\n"
        "- `ChatGPT`\n"
        "- `Cursor AI`\n"
        "- `Docker Hub`\n"
        "- `PineCone AI`\n"
        "- `Langwatch AI`\n\n"
        "Behavior:\n"
        "- one row represents one employee-platform assignment\n"
        "- the same employee can appear on multiple rows for different platforms\n"
        "- duplicate active or pending assignments are skipped\n"
        "- if even one row is invalid, the response highlights it using `has_errors`, `error_row_numbers`, and `summary_message`\n"
        "- row-level errors are logged with the exact row context and returned in the response\n"
        "- exact platform names are preferred; aliases are only best-effort fallbacks"
    ),
    responses={
        200: {
            "description": "Bulk import processed successfully. Review `row_results` for per-row outcomes.",
        },
        400: {
            "description": "Invalid CSV, missing required headers, unsupported file type, or malformed content.",
            "content": {
                "application/json": {
                    "example": {"detail": "CSV file must include a StaffID column."}
                }
            },
        },
        422: {
            "description": "Request validation failed for multipart form fields.",
        },
        500: {
            "description": "Unexpected server or database error while processing the CSV.",
        },
    },
)
async def bulk_import_licenses(
    file: Annotated[
        UploadFile,
        File(
            ...,
            description=(
                "CSV file with headers: User Name, Email ID, Platform, StaffID, Emp_newID. "
                "Only .csv files are accepted."
            ),
        ),
    ],
    requested_by_user_id: Annotated[
        int,
        Form(description="Application user ID recorded as the actor for the import and audit trail."),
    ],
    effective_date: Annotated[
        date | None,
        Form(description="Optional effective date to apply to all inserted allocations. Defaults to today."),
    ] = None,
    dry_run: Annotated[
        bool,
        Form(description="When true, validates every row and returns outcomes without committing any database changes."),
    ] = False,
    db: Session = Depends(get_db),
) -> BulkImportResponse:
    """Process a bulk CSV upload for platform license assignment."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported.",
        )

    validate_user_exists(db, requested_by_user_id, "requested_by_user_id")

    try:
        csv_bytes = await file.read()
        csv_rows = parse_csv_rows(csv_bytes)
        if not csv_rows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file has no data rows.",
            )

        summary = run_bulk_license_import(
            db,
            csv_rows=csv_rows,
            requested_by_user_id=requested_by_user_id,
            effective_date=effective_date,
            dry_run=dry_run,
        )
        return BulkImportResponse(
            total_rows=summary.total_rows,
            inserted_count=summary.inserted_count,
            skipped_duplicate_count=summary.skipped_duplicate_count,
            exception_count=summary.exception_count,
            failed_count=summary.failed_count,
            has_errors=summary.has_errors,
            error_row_numbers=summary.error_row_numbers,
            summary_message=summary.summary_message,
            accepted_platform_names=summary.accepted_platform_names,
            row_results=[BulkImportRowResult(**vars(result)) for result in summary.row_results],
        )
    except HTTPException:
        raise
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to decode CSV file. Use UTF-8 encoding.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "bulk CSV import")
    except Exception as exc:
        handle_unexpected_error(db, exc, "bulk CSV import")