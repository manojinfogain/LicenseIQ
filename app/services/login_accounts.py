"""Load and verify login accounts stored in LicenseIQ database."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.password_hash import verify_password
from app.models.login_account import LoginAccount


@dataclass(frozen=True)
class AuthenticatedLoginAccount:
    email: str
    role_code: str
    role_name: str


def verify_login_credentials(
    db: Session,
    email: str,
    password: str,
) -> AuthenticatedLoginAccount | None:
    normalized = (email or "").strip().lower()
    if not normalized or not password:
        return None

    account = db.scalar(
        select(LoginAccount).where(
            func.lower(LoginAccount.email) == normalized,
            LoginAccount.is_active == True,  # noqa: E712
        )
    )
    if not account or not verify_password(password, account.password_hash):
        return None

    return AuthenticatedLoginAccount(
        email=normalized,
        role_code=account.role_code,
        role_name=account.role_display_name,
    )


def list_active_login_emails(db: Session) -> frozenset[str]:
    rows = db.scalars(
        select(LoginAccount.email).where(LoginAccount.is_active == True)  # noqa: E712
    ).all()
    return frozenset((row or "").strip().lower() for row in rows if row)
