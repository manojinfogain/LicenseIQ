"""
Authentication and HTTPS-redirect middleware.

SSOAuthMiddleware
-----------------
Intercepts every request and enforces that the caller has an active session.
Public paths and path prefixes are exempt from the check.

  - API routes (/api/*)  →  401 JSON response when unauthenticated.
  - All other routes     →  302 redirect to /landing.

HTTPSRedirectMiddleware
-----------------------
Redirects plain HTTP requests to HTTPS.  Only active when APP_ENV != "dev"
so local development is not affected.
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.types import ASGIApp

from app.core.audit_logger import audit_log, AuditEventType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public paths that require no authentication
# ---------------------------------------------------------------------------
_PUBLIC_PATHS: frozenset[str] = frozenset(
    {"/login", "/auth/callback", "/logout", "/landing", "/docs", "/openapi.json", "/redoc"}
)

# Path *prefixes* whose sub-paths are all public (e.g. /static/css/style.css)
_PUBLIC_PREFIXES: tuple[str, ...] = ("/static",)


class SSOAuthMiddleware(BaseHTTPMiddleware):
    """Reject or redirect unauthenticated requests to protected routes."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        path = request.url.path

        # Allow public paths and prefixes through without checking the session
        if path in _PUBLIC_PATHS or path.startswith(_PUBLIC_PREFIXES):
            return await call_next(request)

        # Check for an authenticated session
        user = request.session.get("user")
        if user:
            return await call_next(request)

        # Unauthenticated — log the access attempt
        source_ip = request.client.host if request.client else "unknown"
        audit_log._log_event(
            event_type=AuditEventType.AUTHZ_CHECK_FAILED,
            severity="WARNING",
            action=f"Unauthorized access attempt to {path}",
            result="blocked",
            reason="Session not authenticated",
            details={
                "path": path,
                "method": request.method,
                "source_ip": source_ip,
            },
        )

        # Unauthenticated — differentiate between API and browser routes
        if path.startswith("/api/"):
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated. Please sign in via /login."},
            )

        return RedirectResponse(url="/landing", status_code=302)


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """
    Redirect HTTP → HTTPS in production.  Skipped when APP_ENV is "dev".
    Add this middleware *before* SSOAuthMiddleware so the redirect fires
    before any auth logic runs.
    """

    def __init__(self, app: ASGIApp, app_env: str = "dev") -> None:
        super().__init__(app)
        self._enforce = app_env.lower() != "dev"

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        if self._enforce and request.url.scheme == "http":
            https_url = request.url.replace(scheme="https")
            return RedirectResponse(url=str(https_url), status_code=301)
        return await call_next(request)
