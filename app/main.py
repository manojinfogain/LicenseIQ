import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.api import api_router
from app.api.csp_middleware import CSPMiddleware
from app.api.middleware import HTTPSRedirectMiddleware
from app.core.config import settings
from app.core.limiter import limiter

# ---------------------------------------------------------------------------
# Rate limiter — shared instance imported by route modules
# ---------------------------------------------------------------------------

app = FastAPI(title=settings.app_name)
app.state.limiter = limiter
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Middleware — order matters: outermost runs first on the way IN
#   1. CSP security headers (on all responses)
#   2. HTTPS redirect  (production only)
#   3. Session         (retained for compatibility with any session usage)
#   4. CORS
#   5. SlowAPI rate-limiting
# ---------------------------------------------------------------------------

app.add_middleware(CSPMiddleware)
app.add_middleware(HTTPSRedirectMiddleware, app_env=settings.app_env)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    https_only=(settings.app_env.lower() != "dev"),
    same_site="lax",
    max_age=28800,  # 8 hours
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SlowAPIMiddleware)

app.include_router(api_router, prefix=settings.api_v1_str)

# Mount static files (CSS, JS, images, etc.)
static_dir = Path(__file__).parent / "frontend" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded. Please slow down and try again later."},
        headers={"Retry-After": "60"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    content: dict[str, object] = {"detail": "Request validation failed."}
    if settings.app_env.lower() == "dev":
        content["errors"] = exc.errors()
    return JSONResponse(status_code=422, content=content)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception for path %s", request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
    )


def _serve_index_html() -> HTMLResponse:
    """Serve index.html with runtime flags (no sensitive data in browser console in production)."""
    frontend_path = Path(__file__).parent / "frontend" / "templates" / "index.html"
    html = frontend_path.read_text(encoding="utf-8")
    is_dev = settings.app_env.lower() == "dev"
    runtime_script = (
        f'<script>window.__LICENSEIQ__={{isDev:{"true" if is_dev else "false"}}};</script>'
    )
    marker = "<!-- LICENSEIQ_RUNTIME_CONFIG -->"
    if marker in html:
        html = html.replace(marker, runtime_script, 1)
    else:
        html = runtime_script + html
    return HTMLResponse(content=html, media_type="text/html")


@app.get("/", response_model=None)
def root():
    """Serve the main dashboard page"""
    frontend_path = Path(__file__).parent / "frontend" / "templates" / "index.html"
    if frontend_path.exists():
        return _serve_index_html()
    return JSONResponse(
        content={"message": f"{settings.app_name} is running (Template not found - development mode)"}
    )
