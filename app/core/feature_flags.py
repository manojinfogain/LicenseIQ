"""
Feature flag configuration for staged stored procedure migration.

Controls whether to use stored procedures for each rollout slice or fall back
to ORM implementations.
"""

import os
from functools import wraps
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

# Feature flags
# Set USE_PHASE1_SPS=true to enable Phase 1 read-only stored procedures.
USE_PHASE1_SPS = os.getenv("USE_PHASE1_SPS", "false").lower() == "true"
# Set USE_PHASE2_PLATFORM_SPS=true to enable Phase 2 platform CRUD procedures.
USE_PHASE2_PLATFORM_SPS = os.getenv("USE_PHASE2_PLATFORM_SPS", "false").lower() == "true"
# Set USE_PHASE3_REQUEST_SPS=true to enable Phase 3 request lifecycle procedures.
USE_PHASE3_REQUEST_SPS = os.getenv("USE_PHASE3_REQUEST_SPS", "false").lower() == "true"
# Set USE_PHASE4_QUEUE_ALERTS_SPS=true to enable Phase 4 queue & alerts procedures.
USE_PHASE4_QUEUE_ALERTS_SPS = os.getenv("USE_PHASE4_QUEUE_ALERTS_SPS", "false").lower() == "true"

def is_phase1_enabled() -> bool:
    """Check if Phase 1 SPs are enabled."""
    return USE_PHASE1_SPS


def is_phase2_platform_enabled() -> bool:
    """Check if Phase 2 platform CRUD SPs are enabled."""
    return USE_PHASE2_PLATFORM_SPS


def is_phase3_request_enabled() -> bool:
    """Check if Phase 3 request lifecycle SPs are enabled."""
    return USE_PHASE3_REQUEST_SPS


def is_phase4_queue_alerts_enabled() -> bool:
    """Check if Phase 4 queue & alerts SPs are enabled."""
    return USE_PHASE4_QUEUE_ALERTS_SPS


def log_sp_usage(operation: str, use_sp: bool) -> None:
    """Log whether SP or ORM was used for an operation."""
    mode = "SP" if use_sp else "ORM"
    logger.debug(f"Dashboard operation '{operation}' using {mode}")


def with_phase1_fallback(orm_fn):
    """
    Decorator that wraps ORM functions to provide SP usage logging.
    
    Usage:
        @with_phase1_fallback
        def get_dashboard_orm(db):
            # ORM implementation
            return data
            
        # Call normally - decorator handles flag checking
        result = get_dashboard_orm(db)
    """
    @wraps(orm_fn)
    def wrapper(*args, **kwargs):
        operation = orm_fn.__name__
        log_sp_usage(operation, False)  # Will be logged as ORM if this path is taken
        return orm_fn(*args, **kwargs)
    return wrapper


class Phase1SPError(Exception):
    """Raised when Phase 1 SP execution fails."""
    pass


class Phase2SPError(Exception):
    """Raised when Phase 2 SP execution fails."""
    pass


class Phase3SPError(Exception):
    """Raised when Phase 3 SP execution fails."""
    pass


class Phase4SPError(Exception):
    """Raised when Phase 4 SP execution fails."""
    pass


def sp_safe_call(db: Session, sp_fn, orm_fn, *args, **kwargs):
    """
    Safely call SP with automatic fallback to ORM.
    
    Args:
        db: SQLAlchemy session
        sp_fn: Phase 1 SP wrapper function
        orm_fn: ORM fallback function
        *args: Arguments to pass to both functions
        **kwargs: Keyword arguments to pass to both functions
    
    Returns:
        Result from SP (if enabled) or ORM
    
    Example:
        from app.services.phase1_sp_wrappers import exec_usp_GetPlatformById
        from app.services.dashboard import get_platform_orm
        
        result = sp_safe_call(
            db,
            lambda: exec_usp_GetPlatformById(db, platform_id),
            lambda: get_platform_orm(db, platform_id),
            platform_id=1
        )
    """
    if not is_phase1_enabled():
        operation = orm_fn.__name__ if hasattr(orm_fn, '__name__') else "ORM"
        log_sp_usage(operation, False)
        return orm_fn(db, *args, **kwargs)
    
    try:
        operation = sp_fn.__name__ if hasattr(sp_fn, '__name__') else "SP"
        result = sp_fn(db, *args, **kwargs)
        log_sp_usage(operation, True)
        return result
    except Exception as exc:
        logger.warning(
            f"Phase 1 SP failed: {exc}. Falling back to ORM.",
            exc_info=True
        )
        operation = orm_fn.__name__ if hasattr(orm_fn, '__name__') else "ORM"
        log_sp_usage(operation, False)
        return orm_fn(db, *args, **kwargs)
