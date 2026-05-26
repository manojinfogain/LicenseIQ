"""
SSO routes — Login, OAuth callback, and Logout.

These endpoints are mounted directly on the root app (not under /api/v1) so
that Azure AD's redirect URI can be a plain path such as /auth/callback.
"""

from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import settings
from app.core.security import cache_tokens, clear_tokens
from app.core.sso import build_auth_url, build_msal_app, is_email_allowed, SSO_SCOPES

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dev-mode stub user injected when SSO_DEV_MODE=true
# ---------------------------------------------------------------------------
_DEV_USER = {"email": "dev@local", "name": "Dev User (local)"}

# ---------------------------------------------------------------------------
# Simple access-denied HTML page (no template dependency)
# ---------------------------------------------------------------------------
_ACCESS_DENIED_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Access Denied — LicenseIQ</title>
  <style>
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:#f5f4f0;display:flex;align-items:center;
         justify-content:center;min-height:100vh;margin:0}
    .card{background:#fff;border:1px solid #e3e0d8;border-radius:14px;
          padding:48px 56px;text-align:center;max-width:440px}
    h1{font-size:22px;color:#1a1a1a;margin-bottom:12px}
    p{color:#6b6b6b;font-size:14px;line-height:1.6;margin-bottom:24px}
    a{display:inline-block;background:#1a1a1a;color:#fff;text-decoration:none;
      padding:10px 28px;border-radius:8px;font-size:13px;font-weight:600}
    a:hover{background:#333}
    .icon{font-size:42px;margin-bottom:20px}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">🔒</div>
    <h1>Access Denied</h1>
    <p>Your account (<strong>{email}</strong>) is not authorised to access LicenseIQ.
       Please contact your administrator to request access.</p>
    <a href="/landing">Back to Login</a>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# GET /login
# ---------------------------------------------------------------------------

@router.get("/login", include_in_schema=False)
async def login(request: Request) -> RedirectResponse:
    """
    Initiate the Azure AD OAuth 2.0 Authorization Code flow.

    In DEV_MODE the SSO round-trip is skipped and a stub dev user is injected
    directly into the session for rapid local development.
    """
    if settings.sso_dev_mode:
        logger.warning(
            "SSO_DEV_MODE is enabled but open dev login is disabled; use the app sign-in form."
        )
        return RedirectResponse(url="/", status_code=302)

    # Generate a cryptographically random CSRF state token and persist it
    # in the session so the callback can validate it.
    state = secrets.token_urlsafe(32)
    request.session["sso_state"] = state

    auth_url = build_auth_url(state=state)
    return RedirectResponse(url=auth_url, status_code=302)


# ---------------------------------------------------------------------------
# GET /auth/callback
# ---------------------------------------------------------------------------

@router.get("/auth/callback", response_model=None, include_in_schema=False)
async def auth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse | HTMLResponse:
    """
    Handle the redirect back from Microsoft after user authentication.

    Steps:
    1. Validate CSRF state.
    2. Exchange the authorization code for tokens via MSAL.
    3. Check the whitelist.
    4. Store tokens server-side; store minimal user info in the session cookie.
    """
    # Surface any IdP-level errors early
    if error:
        logger.warning("Azure AD returned error: %s — %s", error, error_description)
        return HTMLResponse(
            content=_ACCESS_DENIED_HTML.format(email=error),
            status_code=403,
        )

    # --- CSRF state validation ---
    expected_state = request.session.pop("sso_state", None)
    if not expected_state or state != expected_state:
        logger.warning("SSO callback CSRF state mismatch — possible CSRF attack")
        return HTMLResponse(
            content=_ACCESS_DENIED_HTML.format(email="(unknown — state mismatch)"),
            status_code=403,
        )

    if not code:
        logger.warning("SSO callback received no authorization code")
        return RedirectResponse(url="/landing", status_code=302)

    # --- Exchange code for tokens ---
    msal_app = build_msal_app()
    result = msal_app.acquire_token_by_authorization_code(
        code=code,
        scopes=SSO_SCOPES,
        redirect_uri=settings.sso_redirect_uri,
    )

    if "error" in result:
        logger.error(
            "MSAL token exchange failed: %s — %s",
            result.get("error"),
            result.get("error_description"),
        )
        return HTMLResponse(
            content=_ACCESS_DENIED_HTML.format(email="(token exchange failed)"),
            status_code=403,
        )

    # --- Extract user identity from id_token_claims ---
    claims: dict = result.get("id_token_claims", {})
    email: str = (
        claims.get("preferred_username")
        or claims.get("email")
        or claims.get("upn")
        or ""
    ).strip().lower()

    display_name: str = claims.get("name", email)

    if not email:
        logger.error("Could not determine user email from id_token_claims: %s", claims)
        return HTMLResponse(
            content=_ACCESS_DENIED_HTML.format(email="(unknown)"),
            status_code=403,
        )

    # --- Whitelist check ---
    if not is_email_allowed(email):
        logger.warning("SSO login denied for unlisted email: %s", email)
        return HTMLResponse(
            content=_ACCESS_DENIED_HTML.format(email=email),
            status_code=403,
        )

    # --- Persist tokens server-side; put only lightweight user info in cookie ---
    cache_tokens(
        email=email,
        access_token=result["access_token"],
        refresh_token=result.get("refresh_token"),
    )
    request.session["user"] = {"email": email, "name": display_name}

    logger.info("SSO login successful for %s", email)
    return RedirectResponse(url="/", status_code=302)


# ---------------------------------------------------------------------------
# GET /logout
# ---------------------------------------------------------------------------

@router.get("/logout", include_in_schema=False)
async def logout(request: Request) -> RedirectResponse:
    """Clear the session and redirect to the landing page."""
    user = request.session.get("user")
    if user:
        clear_tokens(user.get("email", ""))
        logger.info("User %s logged out", user.get("email"))
    request.session.clear()
    return RedirectResponse(url="/landing", status_code=302)


# ---------------------------------------------------------------------------
# GET /landing
# ---------------------------------------------------------------------------

@router.get("/landing", include_in_schema=False)
async def landing() -> HTMLResponse:
    """Public landing / login page shown to unauthenticated visitors."""
    html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>LicenseIQ — Sign In</title>
  <style>
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:#f5f4f0;display:flex;align-items:center;
         justify-content:center;min-height:100vh;margin:0}
    .card{background:#fff;border:1px solid #e3e0d8;border-radius:14px;
          padding:56px 64px;text-align:center;max-width:400px}
    .logo{width:52px;height:52px;background:#1a1a1a;border-radius:12px;
          display:inline-flex;align-items:center;justify-content:center;
          font-size:20px;font-weight:900;color:#fff;margin-bottom:20px}
    h1{font-size:24px;font-weight:800;color:#1a1a1a;margin-bottom:8px}
    p{color:#6b6b6b;font-size:13px;margin-bottom:32px}
    a{display:flex;align-items:center;justify-content:center;gap:10px;
      background:#0067b8;color:#fff;text-decoration:none;
      padding:12px 28px;border-radius:8px;font-size:14px;font-weight:600;
      transition:background .15s}
    a:hover{background:#005a9e}
    .ms-logo{font-size:18px}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">IQ</div>
    <h1>LicenseIQ</h1>
    <p>Sign in with your Infogain Microsoft account to continue.</p>
    <a href="/login">
      <span class="ms-logo">⊞</span>
      Sign in with Microsoft
    </a>
  </div>
</body>
</html>
"""
    return HTMLResponse(content=html)
