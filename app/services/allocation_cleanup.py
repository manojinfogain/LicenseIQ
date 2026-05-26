import hashlib
import time
from sqlalchemy import select, delete
from app.models.license import LicenseAllocation, AllocationAudit, LicenseRequest, QueueItem
from app.models.license import Alert
from app.models.license import ApprovalHistory
from sqlalchemy.orm import Session

def _generate_confirm_token(counts: dict) -> str:
    # Simple hash of counts + timestamp
    raw = str(counts) + str(int(time.time() // 60))  # 1-min window
    return hashlib.sha256(raw.encode()).hexdigest()

def dry_run_allocation_cleanup(db: Session) -> dict:
    # Gather all affected IDs
    allocation_ids = [row[0] for row in db.execute(select(LicenseAllocation.id)).all()]
    request_ids = [row[0] for row in db.execute(select(LicenseRequest.id)).all()]
    queue_ids = [row[0] for row in db.execute(select(QueueItem.id)).all()]
    audit_ids = [row[0] for row in db.execute(select(AllocationAudit.id)).all()]
    alert_ids = [row[0] for row in db.execute(select(Alert.id)).all()]
    approval_ids = [row[0] for row in db.execute(select(ApprovalHistory.id)).all()]
    counts = {
        "license_allocations": len(allocation_ids),
        "allocation_audits": len(audit_ids),
        "license_requests": len(request_ids),
        "approval_histories": len(approval_ids),
        "queue_items": len(queue_ids),
        "alerts": len(alert_ids),
    }
    return {"counts": counts, "confirm_token": _generate_confirm_token(counts)}

def execute_allocation_cleanup(db: Session, confirm_token: str, requested_by_user_id: int, reason: str | None) -> dict:
    # Recompute counts and validate token
    counts = dry_run_allocation_cleanup(db)["counts"]
    expected_token = _generate_confirm_token(counts)
    if confirm_token != expected_token:
        raise Exception("Invalid or expired confirm_token. Please re-run dry_run.")
    # Delete in FK-safe order
    db.execute(delete(ApprovalHistory))
    db.execute(delete(AllocationAudit))
    db.execute(delete(QueueItem))
    db.execute(delete(LicenseRequest))
    db.execute(delete(Alert))
    db.execute(delete(LicenseAllocation))
    db.commit()
    return {"counts": counts}
