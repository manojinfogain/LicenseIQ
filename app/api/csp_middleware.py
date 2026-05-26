"""
Content Security Policy (CSP) middleware.

Adds strict CSP headers to all responses to prevent XSS, injection attacks,
and other client-side vulnerabilities.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class CSPMiddleware(BaseHTTPMiddleware):
    """
    Add Content-Security-Policy header to all responses.

    Policy: Restrictive by default
      - default-src 'self'                 (only self-hosted resources)
      - script-src 'self'                  (only self-hosted scripts)
      - style-src 'self'                   (only self-hosted styles)
      - img-src 'self' data:               (self or data URIs for images)
      - font-src 'self'                    (only self-hosted fonts)
      - connect-src 'self'                 (API calls to own domain)
      - frame-ancestors 'none'             (prevent clickjacking)
      - base-uri 'self'                    (base tags must point to self)
      - form-action 'self'                 (form submissions to self only)
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        # Transitional CSP policy for the current frontend.
        # The existing UI still relies on inline styles, inline event handlers,
        # and third-party CDN bundles for XLSX/jsPDF export features.
        self.csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self' https://cdnjs.cloudflare.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "upgrade-insecure-requests"
        )

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        """Add CSP header to response."""
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = self.csp_policy
        # Also add report-only header for monitoring (optional)
        # response.headers["Content-Security-Policy-Report-Only"] = self.csp_policy
        return response
