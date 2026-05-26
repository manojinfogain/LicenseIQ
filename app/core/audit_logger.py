"""
Audit logging for security-relevant events.

Logs authentication attempts, role changes, permission checks, and sensitive
data access with full context (user, timestamp, action, result).

In production, these logs should be sent to a centralized logging service
(Azure Application Insights, ELK, Splunk, etc.) with tamper-proof storage
and 90+ day retention policy.
"""

import logging
import json
from datetime import datetime
from typing import Any, Optional
from enum import Enum


class AuditEventType(Enum):
    """Types of security-relevant events to audit."""
    
    # Authentication events
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILURE = "auth.login.failure"
    AUTH_LOGOUT = "auth.logout"
    
    # Authorization events
    AUTHZ_CHECK_PASSED = "authz.check.passed"
    AUTHZ_CHECK_FAILED = "authz.check.failed"
    AUTHZ_ROLE_ASSIGNED = "authz.role.assigned"
    AUTHZ_ROLE_CHANGED = "authz.role.changed"
    AUTHZ_ROLE_REVOKED = "authz.role.revoked"
    
    # Data access events
    DATA_ACCESS_SENSITIVE = "data.access.sensitive"
    DATA_EXPORT = "data.export"
    DATA_MODIFICATION = "data.modification"
    
    # Configuration events
    CONFIG_CHANGE = "config.change"
    SECRET_ROTATION = "secret.rotation"


class AuditLogger:
    """
    Structured audit logging for security events.
    
    Usage:
        audit_log = AuditLogger(__name__)
        audit_log.log_auth_success(email="user@example.com", staffid="12345")
        audit_log.log_authz_check_failed(user_id=1, required_role="gdl")
    """

    def __init__(self, logger_name: str = "audit") -> None:
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)

    def _log_event(
        self,
        event_type: AuditEventType,
        severity: str = "INFO",
        user_email: Optional[str] = None,
        user_id: Optional[int] = None,
        staffid: Optional[str] = None,
        action: Optional[str] = None,
        result: str = "success",
        reason: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Log a security-relevant event with structured context.

        Args:
            event_type: Type of security event (from AuditEventType enum)
            severity: Log level (INFO, WARNING, ERROR, CRITICAL)
            user_email: Email address of the user (for traceability)
            user_id: Database ID of the user
            staffid: Staff ID of the user (from Aspire)
            action: Human-readable description of the action
            result: Result of the action ("success", "failure", "blocked", etc.)
            reason: Reason for the result (especially failures)
            details: Additional context as dict (will be JSON serialized)
        """
        audit_record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type.value,
            "severity": severity,
            "result": result,
            "user_email": user_email,
            "user_id": user_id,
            "staffid": staffid,
            "action": action,
            "reason": reason,
            **(details or {}),
        }

        # Remove None values for cleaner output
        audit_record = {k: v for k, v in audit_record.items() if v is not None}

        # Log as JSON for easy parsing by SIEM/log aggregation tools
        log_message = json.dumps(audit_record)

        if severity == "CRITICAL":
            self.logger.critical(log_message)
        elif severity == "ERROR":
            self.logger.error(log_message)
        elif severity == "WARNING":
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)

    # =========================================================================
    # Authentication logging
    # =========================================================================

    def log_auth_success(
        self,
        email: str,
        staffid: str,
        user_id: Optional[int] = None,
        role: Optional[str] = None,
    ) -> None:
        """Log successful authentication."""
        self._log_event(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            severity="INFO",
            user_email=email,
            staffid=staffid,
            user_id=user_id,
            action=f"User logged in successfully",
            result="success",
            details={"role": role} if role else None,
        )

    def log_auth_failure(
        self,
        email: str,
        reason: str,
        source_ip: Optional[str] = None,
    ) -> None:
        """Log failed authentication attempt."""
        self._log_event(
            event_type=AuditEventType.AUTH_LOGIN_FAILURE,
            severity="WARNING",
            user_email=email,
            action="Login attempt failed",
            result="failure",
            reason=reason,
            details={"source_ip": source_ip} if source_ip else None,
        )

    def log_auth_logout(
        self,
        email: str,
        user_id: Optional[int] = None,
    ) -> None:
        """Log user logout."""
        self._log_event(
            event_type=AuditEventType.AUTH_LOGOUT,
            severity="INFO",
            user_email=email,
            user_id=user_id,
            action="User logged out",
            result="success",
        )

    # =========================================================================
    # Authorization logging
    # =========================================================================

    def log_authz_check_passed(
        self,
        user_email: str,
        required_role: str,
        user_role: str,
        resource: str,
    ) -> None:
        """Log successful authorization check."""
        self._log_event(
            event_type=AuditEventType.AUTHZ_CHECK_PASSED,
            severity="INFO",
            user_email=user_email,
            action=f"Authorization check passed for {resource}",
            result="success",
            details={
                "required_role": required_role,
                "user_role": user_role,
                "resource": resource,
            },
        )

    def log_authz_check_failed(
        self,
        user_email: str,
        required_role: str,
        user_role: Optional[str] = None,
        resource: str = "unknown",
    ) -> None:
        """Log failed authorization check (access denied)."""
        self._log_event(
            event_type=AuditEventType.AUTHZ_CHECK_FAILED,
            severity="WARNING",
            user_email=user_email,
            action=f"Authorization check failed for {resource}",
            result="blocked",
            reason=f"User role '{user_role}' does not have '{required_role}' permission",
            details={
                "required_role": required_role,
                "user_role": user_role,
                "resource": resource,
            },
        )

    def log_role_assigned(
        self,
        target_email: str,
        target_staffid: str,
        role_code: str,
        assigned_by_email: Optional[str] = None,
    ) -> None:
        """Log role assignment."""
        self._log_event(
            event_type=AuditEventType.AUTHZ_ROLE_ASSIGNED,
            severity="INFO",
            user_email=target_email,
            staffid=target_staffid,
            action=f"Role '{role_code}' assigned",
            result="success",
            details={"assigned_by": assigned_by_email} if assigned_by_email else None,
        )

    def log_role_changed(
        self,
        target_email: str,
        target_staffid: str,
        old_role: str,
        new_role: str,
        changed_by_email: Optional[str] = None,
    ) -> None:
        """Log role change."""
        self._log_event(
            event_type=AuditEventType.AUTHZ_ROLE_CHANGED,
            severity="INFO",
            user_email=target_email,
            staffid=target_staffid,
            action=f"Role changed from '{old_role}' to '{new_role}'",
            result="success",
            details={"changed_by": changed_by_email} if changed_by_email else None,
        )

    def log_role_revoked(
        self,
        target_email: str,
        target_staffid: str,
        role_code: str,
        revoked_by_email: Optional[str] = None,
    ) -> None:
        """Log role revocation."""
        self._log_event(
            event_type=AuditEventType.AUTHZ_ROLE_REVOKED,
            severity="INFO",
            user_email=target_email,
            staffid=target_staffid,
            action=f"Role '{role_code}' revoked",
            result="success",
            details={"revoked_by": revoked_by_email} if revoked_by_email else None,
        )

    # =========================================================================
    # Data access logging
    # =========================================================================

    def log_sensitive_data_access(
        self,
        user_email: str,
        user_role: str,
        data_type: str,
        record_count: int = 1,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Log access to sensitive data.

        Args:
            user_email: Email of user accessing data
            user_role: Role of user
            data_type: Type of sensitive data (e.g., "employee_list", "allocations", "contracts")
            record_count: Number of records accessed
            details: Additional context
        """
        self._log_event(
            event_type=AuditEventType.DATA_ACCESS_SENSITIVE,
            severity="INFO",
            user_email=user_email,
            action=f"Accessed {record_count} {data_type} records",
            result="success",
            details={
                "data_type": data_type,
                "record_count": record_count,
                "user_role": user_role,
                **(details or {}),
            },
        )

    def log_data_modification(
        self,
        user_email: str,
        user_role: str,
        action_type: str,
        table_name: str,
        record_id: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Log data modification (insert, update, delete).

        Args:
            user_email: Email of user modifying data
            user_role: Role of user
            action_type: "create", "update", or "delete"
            table_name: Table being modified
            record_id: ID of record being modified
            details: Additional context (old values, new values, etc.)
        """
        self._log_event(
            event_type=AuditEventType.DATA_MODIFICATION,
            severity="INFO",
            user_email=user_email,
            action=f"Modified {table_name} (action: {action_type})",
            result="success",
            details={
                "action_type": action_type,
                "table_name": table_name,
                "record_id": record_id,
                "user_role": user_role,
                **(details or {}),
            },
        )


# Create a global audit logger instance
audit_log = AuditLogger("audit")
