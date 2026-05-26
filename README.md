# LicenseIQ

License intelligence and lifecycle management with role-scoped dashboards, multi-stage request approvals, queue execution, and smart alerts driven by Aspire HRMS data.

## Overview

LicenseIQ is a **FastAPI** application backed by **SQL Server**:

- Reads workforce and project data from **Aspire** (read-only).
- Stores licenses, requests, queue items, and alerts in the **LicenseIQ** database.
- Supports **assign / revoke** workflows with role-based scoping (GDL, account owner, PM, finance, admin).
- Syncs **smart alerts** from Aspire events (exit, project change, bench).
- Can roll out read/write paths via **stored procedures** (feature flags).

## Architecture

```text
Browser (index.html + app.js + security.js)
        |
        v
FastAPI (app/main.py)
  |- Middleware: CSP, HTTPS (prod), session, CORS, rate limits
  |- API: auth, dashboard, employees, platforms, alerts, requests, queue, bulk-import, SSO
  |- Services: dashboard, aspire, pricing, approval_workflow, license_execution, employee_resolution
        |
        +--> LicenseIQ DB (read/write)
        |
        +--> Aspire DB (read-only)
```

## Request approval workflow

Typical path when a **project manager** raises a license request:

| Step | Role | Action | License register |
|------|------|--------|------------------|
| 1 | PM / manager | Submit assign request | No change yet |
| 2 | Account owner | Approve on **Approvals** | Request moves to IT Admin only |
| 3 | IT admin | Approve on **Queue** (pending IT Admin) | **License is created** and appears in register |

Account owners, GDL, and IT admin may use **self-approve** paths that skip step 2 and go straight to the IT Admin queue. Details are in `app/services/approval_workflow.py`.

Employee references on requests are normalized to local `employees.id` on create and on IT Admin approval (`app/services/employee_resolution.py`) so allocations show correctly in the license register.

## Project layout

```text
app/
  api/routes/          # REST endpoints
  core/                # config, DB, SSO, security, audit, rate limiter
  frontend/            # index.html, static JS/CSS
  models/              # SQLAlchemy models (incl. login_accounts)
  schemas/             # Pydantic request/response models
  services/            # business logic (dashboard, aspire, phases, pricing, …)
  main.py

sql/                   # migrations and stored-procedure scripts
tests/                 # pytest suite (see tests/README.md)
  unit/ auth/ dashboard/ scoping/ phases/
docs/                  # security and SP implementation notes
pytest.ini
requirements.txt
.env.example           # template — copy to .env (never commit .env)
```

Generated reports, local scripts, and `venv/` are **not** committed (see `.gitignore`).

## Requirements

- Python **3.11+**
- **ODBC Driver 17 or 18** for SQL Server
- Access to LicenseIQ and Aspire SQL Server instances

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Environment setup

Copy [.env.example](.env.example) to `.env` and set real values.

**Required (minimum):**

```env
APP_NAME=LicenseIQ API
APP_ENV=dev
API_V1_STR=/api/v1
BACKEND_CORS_ORIGINS=http://127.0.0.1:8000

DB_SERVER=YOUR_SQL_HOST
DB_PORT=1433
DB_NAME=LicenseIQ
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_DRIVER=ODBC Driver 18 for SQL Server
DB_TRUST_SERVER_CERTIFICATE=true

ASPIRE_DB_SERVER=YOUR_ASPIRE_HOST
ASPIRE_DB_NAME=Aspire
ASPIRE_DB_USER=your_aspire_user
ASPIRE_DB_PASSWORD=your_aspire_password

SESSION_SECRET_KEY=use-a-long-random-secret
AUTH_ASPIRE_AUTO_ROLE=true
```

**Optional:** Azure AD SSO (`SSO_*`), email (`EMAIL_*`). See [app/core/config.py](app/core/config.py) for all settings.

If `ASPIRE_DB_*` is omitted, Aspire connection falls back to `DB_*` where applicable.

## Database setup

```bash
# Create schema / seed reference data (as used in your environment)
python -m app.init_db
python app/seed_db.py

# Login accounts (hashed passwords only — apply in SQL Server)
# sql/migration_add_login_accounts.sql
```

## Run locally

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- App: http://127.0.0.1:8000  
- API docs: http://127.0.0.1:8000/docs  

In production (`APP_ENV` not `dev`), HTTPS redirect and stricter API error responses are enabled; the UI loads `security.js` to reduce sensitive browser console output.

## Authentication

1. **Email + password** — active rows in `login_accounts` (passwords stored as PBKDF2 hashes only).
2. User must exist in Aspire **ERM_EMPLOYEE_MASTER** (matched by email).
3. **Role** from `employee_wise_role_mappings`, or from Aspire org data when `AUTH_ASPIRE_AUTO_ROLE=true` (GDL, account owner, PM).

Optional: **Azure AD SSO** via `/auth/callback` when `SSO_*` variables are configured.

## Key API areas

| Area | Prefix |
|------|--------|
| Auth | `/api/v1/auth` |
| Dashboard | `/api/v1/dashboard` |
| Employees | `/api/v1/employees` |
| Platforms | `/api/v1/platforms` |
| Alerts | `/api/v1/alerts` |
| Requests | `/api/v1/requests` |
| Queue | `/api/v1/queue` |
| Bulk import | `/api/v1/bulk-import` |
| Allocation cleanup | `/api/v1/allocation-cleanup` |
| Health | `/api/v1/health` |

## Stored procedures (optional)

Controlled by flags in [app/core/feature_flags.py](app/core/feature_flags.py):

- `USE_PHASE1_SPS` — reads (alerts, requests, queue, role mapping)
- `USE_PHASE2_PLATFORM_SPS` — platform CRUD
- `USE_PHASE3_REQUEST_SPS` — request lifecycle
- `USE_PHASE4_QUEUE_ALERTS_SPS` — queue + alerts

SQL scripts live under [sql/](sql).

## Smart alerts

Sync recent Aspire HR events (exit, project release, bench):

```http
POST /api/v1/alerts/aspire-sync?lookback_days=30
```

Service: [app/services/aspire_events.py](app/services/aspire_events.py).

## Testing

Requires a reachable LicenseIQ database (integration tests).

```bash
python -m pytest tests -v --tb=short
python tests/run_tests.py              # core subset
python tests/run_tests.py --all -v     # full tree
```

Layout and commands: [tests/README.md](tests/README.md).

## Documentation

- [docs/SECURITY_ENHANCEMENTS.md](docs/SECURITY_ENHANCEMENTS.md) — CSP, audit logging
- [docs/SP_IMPLEMENTATION_PLAN.md](docs/SP_IMPLEMENTATION_PLAN.md) — stored procedure rollout

## Before pushing to GitHub

1. Never commit `.env` or credentials.
2. Keep `venv/`, `reports/`, and local `scripts/` out of git (see `.gitignore`).
3. Use `.env.example` as the template for new developers.
