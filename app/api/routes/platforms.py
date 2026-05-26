from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.error_utils import handle_database_error, handle_unexpected_error
from app.models.platform import Platform, PlatformContract
from app.schemas.platform import PlatformCreate, PlatformRead
from app.services.phase1_integration import get_platform_by_id_phase1
from app.services.phase2_integration import (
    create_platform_phase2,
    delete_platform_phase2,
    update_platform_phase2,
)


router = APIRouter()


@router.get("", response_model=list[PlatformRead])
def list_platforms(db: Session = Depends(get_db)) -> list[PlatformRead]:
    try:
        return list(db.scalars(select(Platform).order_by(Platform.name)).all())
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "list platforms")
    except Exception as exc:
        handle_unexpected_error(db, exc, "list platforms")


@router.post("", response_model=PlatformRead, status_code=status.HTTP_201_CREATED)
def create_platform(payload: PlatformCreate, db: Session = Depends(get_db)) -> PlatformRead:
    try:
        return create_platform_phase2(db, payload)
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "create platform")
    except Exception as exc:
        handle_unexpected_error(db, exc, "create platform")


@router.get("/{platform_id}", response_model=PlatformRead)
def get_platform(platform_id: int, db: Session = Depends(get_db)) -> PlatformRead:
    try:
        # Try Phase 1 SP first (if enabled), falls back to ORM
        platform_data = get_platform_by_id_phase1(db, platform_id)
        if platform_data:
            # SP returns dict, convert to Platform ORM for consistency
            platform = db.get(Platform, platform_id)
            if platform:
                return platform
        
        # Fallback: direct ORM query
        platform = db.get(Platform, platform_id)
        if not platform:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")
        return platform
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "get platform")
    except Exception as exc:
        handle_unexpected_error(db, exc, "get platform")


@router.put("/{platform_id}", response_model=PlatformRead)
def update_platform(platform_id: int, payload: PlatformCreate, db: Session = Depends(get_db)) -> PlatformRead:
    try:
        return update_platform_phase2(db, platform_id, payload)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "update platform")
    except Exception as exc:
        handle_unexpected_error(db, exc, "update platform")


@router.delete("/{platform_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_platform(platform_id: int, db: Session = Depends(get_db)) -> None:
    try:
        delete_platform_phase2(db, platform_id)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        handle_database_error(db, exc, "delete platform")
    except Exception as exc:
        handle_unexpected_error(db, exc, "delete platform")
