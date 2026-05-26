import logging

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


def rollback_session(db: Session) -> None:
    try:
        db.rollback()
    except Exception:
        logger.exception("Failed to rollback database session")


def handle_database_error(db: Session, exc: SQLAlchemyError, context: str) -> None:
    rollback_session(db)
    logger.exception("Database error during %s", context, exc_info=exc)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="A database error occurred while processing the request.",
    ) from exc


def handle_unexpected_error(db: Session, exc: Exception, context: str) -> None:
    rollback_session(db)
    logger.exception("Unexpected error during %s", context, exc_info=exc)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected server error occurred.",
    ) from exc