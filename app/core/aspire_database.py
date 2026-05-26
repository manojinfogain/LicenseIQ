from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class AspireBase(DeclarativeBase):
    pass


aspire_engine = create_engine(settings.aspire_database_url, future=True, pool_pre_ping=True)
AspireSessionLocal = sessionmaker(bind=aspire_engine, autocommit=False, autoflush=False, future=True)


def get_aspire_db():
    db = AspireSessionLocal()
    try:
        yield db
    finally:
        db.close()
