"""
Server-side token store and Graph API token management.

Access tokens and refresh tokens are intentionally kept OUT of the browser
session cookie (which has a 4 KB limit).  They are stored in this module's
in-memory dictionary, keyed by the user's email address.

In a multi-worker deployment this store should be replaced with a shared
cache such as Redis.  For single-worker deployments (development / small
production) the in-memory dict is sufficient.
"""

from __future__ import annotations

import logging
from typing import Any

from starlette.requests import Request

from app.core.sso import SSO_SCOPES, build_msal_app

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory token store: { email -> {"access_token": str, "refresh_token": str} }
# ---------------------------------------------------------------------------
_token_store: dict[str, dict[str, str]] = {}


def cache_tokens(email: str, access_token: str, refresh_token: str | None) -> None:
    """Persist tokens for *email* in the server-side store."""
    _token_store[email.lower()] = {
        "access_token": access_token,
        "refresh_token": refresh_token or "",
    }


def clear_tokens(email: str) -> None:
    """Remove all cached tokens for *email* (called on logout)."""
    _token_store.pop(email.lower(), None)


# ---------------------------------------------------------------------------
# Token retrieval helpers
# ---------------------------------------------------------------------------

def _refresh_via_msal(refresh_token: str) -> dict[str, Any] | None:
    """
    Exchange *refresh_token* for a new token set via MSAL silent refresh.
    Returns the full MSAL result dict, or None if the refresh failed.
    """
    msal_app = build_msal_app()
    result = msal_app.acquire_token_by_refresh_token(
        refresh_token=refresh_token,
        scopes=SSO_SCOPES,
    )
    if "access_token" in result:
        return result
    logger.warning("MSAL silent refresh failed: %s", result.get("error_description"))
    return None


def get_graph_token(request: Request) -> str | None:
    """
    Return a valid Microsoft Graph access token for the currently logged-in
    user.  Falls back to a silent refresh if the cached token is absent.

    Returns None when no valid token can be obtained (caller should treat
    the user as unauthenticated).
    """
    user: dict | None = request.session.get("user")
    if not user:
        return None

    email: str = user["email"].lower()
    stored = _token_store.get(email, {})

    access_token = stored.get("access_token")
    if access_token:
        return access_token

    # No access token — attempt silent refresh
    refresh_token = stored.get("refresh_token")
    if not refresh_token:
        logger.debug("No refresh token available for %s", email)
        return None

    result = _refresh_via_msal(refresh_token)
    if result:
        new_access = result["access_token"]
        new_refresh = result.get("refresh_token", refresh_token)
        cache_tokens(email, new_access, new_refresh)
        return new_access

    return None


def refresh_token_for_scheduler(refresh_token: str) -> str | None:
    """
    Perform a silent MSAL token refresh outside of a request context
    (for use by background / scheduled tasks).

    Returns the new access token, or None if the refresh failed.
    The caller is responsible for persisting the new token via cache_tokens().
    """
    result = _refresh_via_msal(refresh_token)
    if result:
        return result["access_token"]
    return None
