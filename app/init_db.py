import re
from pathlib import Path

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.core.database import Base, engine
from app.db.base import import_models


SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
APP_DB_MIGRATION_GLOB = "migration_*.sql"
SKIP_APP_DB_MIGRATIONS = {"migration_add_aspire_event_procedures.sql"}


def _split_sql_batches(script_text: str) -> list[str]:
    return [batch.strip() for batch in re.split(r"^GO\s*$", script_text, flags=re.MULTILINE | re.IGNORECASE) if batch.strip()]


def _iter_app_db_migration_paths() -> list[Path]:
    return [
        path
        for path in sorted(SQL_DIR.glob(APP_DB_MIGRATION_GLOB))
        if path.name not in SKIP_APP_DB_MIGRATIONS
    ]


def ensure_database_exists() -> None:
    database_name = settings.db_name
    if not re.fullmatch(r"[A-Za-z0-9_]+", database_name):
        raise ValueError("DB_NAME must contain only letters, numbers, or underscores.")

    master_engine = create_engine(settings.master_database_url, future=True, pool_pre_ping=True)
    statement = text(
        f"IF DB_ID(N'{database_name}') IS NULL BEGIN CREATE DATABASE [{database_name}] END"
    )
    with master_engine.connect() as connection:
        connection.execution_options(isolation_level="AUTOCOMMIT").execute(statement)


def create_tables() -> None:
    import_models()
    Base.metadata.create_all(bind=engine)


def apply_app_database_migrations() -> None:
    migration_paths = _iter_app_db_migration_paths()
    if not migration_paths:
        return

    raw_connection = engine.raw_connection()
    try:
        raw_connection.autocommit = True
        cursor = raw_connection.cursor()
        for path in migration_paths:
            batches = _split_sql_batches(path.read_text(encoding="utf-8"))
            for batch in batches:
                cursor.execute(batch)
        cursor.close()
    finally:
        raw_connection.close()


def main() -> None:
    ensure_database_exists()
    create_tables()
    apply_app_database_migrations()
    print(f"Database '{settings.db_name}' is ready.")


if __name__ == "__main__":
    main()
