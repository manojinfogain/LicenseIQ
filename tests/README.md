# LicenseIQ test suite

Tests are grouped by area. Run everything from the project root (`licenseIQ/`).

## Layout

| Folder | Purpose |
|--------|---------|
| `unit/` | Fast unit tests (no database), e.g. pricing, password helpers |
| `auth/` | Login and role behaviour |
| `dashboard/` | Dashboard metrics, bootstrap integrity, distribution |
| `scoping/` | Role-based data scoping |
| `phases/phase1` … `phase4` | Stored-procedure and integration tests by rollout phase |
| `manual/` | Exploratory / debug scripts (not collected by pytest) |
| `scripts/` | Standalone runner scripts (wrapper smoke tests, fresh-data checks) |

Shared fixtures: `conftest.py` (project root of `tests/`).

## Commands

```bash
# All pytest tests (excludes manual/ and scripts/)
python -m pytest

# Verbose
python -m pytest -v

# By area
python -m pytest tests/unit -v
python -m pytest tests/scoping -v
python -m pytest tests/dashboard -v
python -m pytest tests/phases/phase1 -v

# Convenience runner (core scoping + metrics + bootstrap)
python tests/run_tests.py
python tests/run_tests.py -v
python tests/run_tests.py -k scoping
```

## Manual / script runners

Not run by `pytest` by default:

```bash
python tests/manual/test_dashboard.py
python tests/scripts/test_wrappers_phase1.py
python tests/scripts/fresh_data_test.py
```
