"""
Azure AD SSO helpers — MSAL ConfidentialClientApplication factory and
authorization URL builder.  All configuration is read from Settings so that
nothing is hard-coded outside of this module.
"""

from __future__ import annotations

import msal

from app.core.config import settings

# ---------------------------------------------------------------------------
# OAuth scopes requested from Microsoft Graph
# ---------------------------------------------------------------------------
SSO_SCOPES: list[str] = ["User.Read", "Mail.Send"]

# ---------------------------------------------------------------------------
# Whitelist of permitted email addresses (case-insensitive comparison).
# Loaded from the SSO_ALLOWED_EMAILS env var (comma-separated).
# Add additional addresses here as a hard-coded fallback/default list.
# ---------------------------------------------------------------------------
_DEFAULT_ALLOWED: set[str] = set()

def _build_allowed_emails() -> frozenset[str]:
    """Return the union of env-var entries and any hard-coded defaults."""
    from_env: set[str] = set()
    if settings.sso_allowed_emails:
        from_env = {
            addr.strip().lower()
            for addr in settings.sso_allowed_emails.split(",")
            if addr.strip()
        }
    return frozenset(_DEFAULT_ALLOWED | from_env)


def is_email_allowed(email: str) -> bool:
    """Return True if *email* has an active row in login_accounts (case-insensitive)."""
    normalized = email.strip().lower()
    if normalized in _build_allowed_emails():
        return True
    from app.core.database import SessionLocal
    from app.services.login_accounts import list_active_login_emails

    db = SessionLocal()
    try:
        return normalized in list_active_login_emails(db)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# MSAL helpers
# ---------------------------------------------------------------------------

def build_msal_app() -> msal.ConfidentialClientApplication:
    """Return a fresh MSAL ConfidentialClientApplication."""
    authority = f"https://login.microsoftonline.com/{settings.sso_tenant_id}"
    return msal.ConfidentialClientApplication(
        client_id=settings.sso_client_id,
        client_credential=settings.sso_client_secret,
        authority=authority,
    )


def build_auth_url(state: str) -> str:
    """
    Build the Microsoft authorization URL the browser should be redirected to.

    *state* is a CSRF token generated per-request and stored in the session.
    """
    msal_app = build_msal_app()
    return msal_app.get_authorization_request_url(
        scopes=SSO_SCOPES,
        state=state,
        redirect_uri=settings.sso_redirect_uri,
    )
