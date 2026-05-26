from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.api.query_helpers import validate_user_exists
from app.services.allocation_cleanup import dry_run_allocation_cleanup, execute_allocation_cleanup

router = APIRouter()

class AllocationCleanupRequest(BaseModel):
    requested_by_user_id: int = Field(..., description="Admin user ID requesting the cleanup.")
    dry_run: bool = Field(..., description="If true, only preview what would be deleted.")
    confirm_token: str | None = Field(None, description="Required only for actual deletion (dry_run=false)")
    reason: str | None = Field(None, description="Optional reason for audit trail.")

class AllocationCleanupResponse(BaseModel):
    dry_run: bool
    requires_confirmation: bool
    confirm_token: str | None
    deleted_counts: dict[str, int]
    message: str

@router.post("/purge", response_model=AllocationCleanupResponse, summary="Purge all allocation-side data (admin)")
def allocation_cleanup_purge(
    payload: AllocationCleanupRequest,
    db: Session = Depends(get_db),
) -> AllocationCleanupResponse:
    validate_user_exists(db, payload.requested_by_user_id, "requested_by_user_id")
    if payload.dry_run:
        result = dry_run_allocation_cleanup(db)
        return AllocationCleanupResponse(
            dry_run=True,
            requires_confirmation=True,
            confirm_token=result["confirm_token"],
            deleted_counts=result["counts"],
            message="Dry run only. No data deleted. Use confirm_token to execute."
        )
    if not payload.confirm_token:
        raise HTTPException(status_code=400, detail="Missing confirm_token for destructive operation.")
    result = execute_allocation_cleanup(db, payload.confirm_token, payload.requested_by_user_id, payload.reason)
    return AllocationCleanupResponse(
        dry_run=False,
        requires_confirmation=False,
        confirm_token=None,
        deleted_counts=result["counts"],
        message="Allocation-side data deleted."
    )
