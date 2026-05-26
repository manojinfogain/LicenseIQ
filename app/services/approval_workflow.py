"""
Approval workflow service for license requests.
Handles self-approval restrictions and multi-stage approval routing.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.access import EmployeeWiseRoleMapping
from app.models.license import ApprovalHistory, LicenseRequest, QueueItem
from app.models.organization import Employee, Project, Account
from app.models.platform import Platform


def get_user_role(db: Session, staffid: str) -> str | None:
    """Get the role code for a user by staff ID (manual mapping or Aspire auto-role)."""
    from app.services.auth_roles import resolve_user_role_code

    return resolve_user_role_code(db, staffid)


def can_self_approve(role: str) -> bool:
    """
    Check if a role can self-approve requests.
    Only Account Owner, GDL, and IT Admin (admin) can self-approve.
    """
    self_approval_roles = ["account_owner", "account", "gdl", "it_admin", "admin"]
    return role in self_approval_roles


def determine_initial_approval_stage(db: Session, request: LicenseRequest, requester_staffid: str) -> tuple[str, int | None]:
    """
    Determine the initial approval stage and assigned user based on requester role.
    
    Returns: (approval_stage, assigned_to_user_id)
    
    Workflow:
    - Account Owner, GDL, IT Admin: Can self-approve → approval_stage = "approved"
    - Project Manager: Must go to Account Owner → approval_stage = "pending_account_owner"
    - Other roles: Must go to Account Owner then IT Admin → approval_stage = "pending_account_owner"
    """
    requester_role = get_user_role(db, requester_staffid)
    
    if not requester_role:
        # Default to Account Owner approval if role not found
        return ("pending_account_owner", None)
    
    # If they can self-approve, approve it immediately
    if can_self_approve(requester_role):
        return ("self_approved", None)
    
    # For all other roles (PM, finance, etc.), route to Account Owner
    # Find the account owner for the requested account/project
    assigned_to_user_id = None
    
    if request.account_id:
        account = db.get(Account, request.account_id)
        if account and account.owner_user_id:
            assigned_to_user_id = account.owner_user_id
    elif request.project_id:
        project = db.get(Project, request.project_id)
        if project and project.account:
            assigned_to_user_id = project.account.owner_user_id
    
    # If account owner not found, get employee's account owner
    if not assigned_to_user_id:
        employee = db.get(Employee, request.employee_id)
        if employee and employee.account_owner_user_id:
            assigned_to_user_id = employee.account_owner_user_id
    
    return ("pending_account_owner", assigned_to_user_id)


def create_queue_item_for_request(
    db: Session,
    request: LicenseRequest,
    approval_stage: str,
    assigned_to_user_id: int | None = None,
    cost_snapshot: float = 0,
) -> QueueItem:
    """Create a queue item for the license request with approval stage."""
    
    # Determine the approval role needed
    if approval_stage == "self_approved":
        # Self-approved by account owner / IT admin: route straight to IT Admin execution queue
        approval_role = "it_admin"
    elif "account_owner" in approval_stage:
        approval_role = "account_owner"
    elif "it_admin" in approval_stage:
        approval_role = "it_admin"
    else:
        approval_role = None
    
    # Get platform info for cost snapshot if needed
    queue_item = QueueItem(
        source_type="request",
        source_id=request.id,
        employee_id=request.employee_id,
        platform_id=request.platform_id,
        action_type=request.request_type,
        project_id=request.project_id,
        cost_snapshot_monthly=cost_snapshot,
        requested_by_user_id=request.requested_by_user_id,
        assigned_to_user_id=assigned_to_user_id,
        status="pending",
        approval_stage="pending_it_admin" if approval_stage == "self_approved" else approval_stage,
        assigned_approval_role=approval_role,
    )
    
    return queue_item


def approve_request_at_stage(
    db: Session,
    request: LicenseRequest,
    approver_user_id: int,
    approver_role: str,
    action: str = "approved",
    notes: str | None = None
) -> bool:
    """
    Approve or reject a request at current stage.
    
    Returns True if approved and moved to next stage, False if rejected.
    """
    # Record approval in history
    approval_record = ApprovalHistory(
        request_id=request.id,
        approval_stage=request.approval_stage,
        approver_user_id=approver_user_id,
        approver_role=approver_role,
        action=action,
        notes=notes
    )
    db.add(approval_record)
    
    if action == "rejected":
        # Reject the request
        request.approval_stage = "rejected"
        request.approval_status = "rejected"
        request.last_approver_user_id = approver_user_id
        request.last_approval_time = db.func.now()
        request.approval_notes = notes
        
        # Update queue item status
        queue_item = db.scalar(
            select(QueueItem)
            .where(QueueItem.source_type == "request")
            .where(QueueItem.source_id == request.id)
        )
        if queue_item:
            queue_item.status = "rejected"
            queue_item.executed_by_user_id = approver_user_id
            queue_item.execution_notes = notes
        
        return False
    
    # Action is "approved"
    if request.approval_stage == "pending_account_owner":
        # Move to IT Admin approval stage
        request.approval_stage = "pending_it_admin"
        request.approval_status = "pending_it_admin"
        request.last_approver_user_id = approver_user_id
        request.last_approval_time = db.func.now()
        
        # Update queue item to be assigned to IT Admin
        queue_item = db.scalar(
            select(QueueItem)
            .where(QueueItem.source_type == "request")
            .where(QueueItem.source_id == request.id)
        )
        if queue_item:
            queue_item.approval_stage = "pending_it_admin"
            queue_item.assigned_approval_role = "it_admin"
            # Find IT Admin user to assign to
            it_admin_mapping = db.scalar(
                select(EmployeeWiseRoleMapping)
                .where(EmployeeWiseRoleMapping.role.has(code="it_admin"))
                .where(EmployeeWiseRoleMapping.is_active == True)
            )
            if it_admin_mapping and hasattr(it_admin_mapping, 'user_id'):
                queue_item.assigned_to_user_id = it_admin_mapping.user_id
        
        return True
    
    elif request.approval_stage == "pending_it_admin":
        # Final approval
        request.approval_stage = "approved"
        request.approval_status = "approved"
        request.last_approver_user_id = approver_user_id
        request.last_approval_time = db.func.now()
        
        # Update queue item
        queue_item = db.scalar(
            select(QueueItem)
            .where(QueueItem.source_type == "request")
            .where(QueueItem.source_id == request.id)
        )
        if queue_item:
            queue_item.status = "approved"
            queue_item.approval_stage = "approved"
            queue_item.executed_by_user_id = approver_user_id
        
        return True
    
    return False
