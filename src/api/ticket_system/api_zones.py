from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.utils.database import get_db, Base, engine, db_session_context
from src.repositories.zone_repository import zone_repository
from src.dto import zone as zone_schemas
from src.utils.cache import invalidate_cache
import logging

router = APIRouter(prefix="/zones", tags=["zones"])

logger = logging.getLogger(__name__)

# Zone endpoints
@router.post("/", response_model=zone_schemas.Zone)
async def create_zone(zone: zone_schemas.ZoneCreate, db: Session = Depends(get_db)):
    db_session_context.set(db)
    try:
        result = await zone_repository.create(zone)
        invalidate_cache(zone.concert_id)
        return result
    except ValueError as e:
        error_msg = str(e)
        if "more zones" in error_msg.lower():
            raise HTTPException(status_code=409, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.error(f"Unexpected error creating zone: {e}")
        raise HTTPException(status_code=500, detail="Failed to create zone")

@router.get("/{zone_id}", response_model=zone_schemas.Zone)
async def read_zone(zone_id: str, db: Session = Depends(get_db)):
    db_session_context.set(db)
    zone = await zone_repository.get(zone_id)
    if not zone:
        logger.error("Zone not found")
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone

@router.put("/{zone_id}", response_model=zone_schemas.Zone)
async def update_zone(zone_id: str, zone: zone_schemas.ZoneUpdate, db: Session = Depends(get_db)):
    db_session_context.set(db)
    existing_zone = await zone_repository.get(zone_id)
    if not existing_zone:
        logger.error("Zone not found for update")
        raise HTTPException(status_code=404, detail="Zone not found")
    updated_zone = await zone_repository.update(zone_id, zone)
    if not updated_zone:
        logger.error("Failed to update zone")
        raise HTTPException(status_code=500, detail="Failed to update zone")
    invalidate_cache(updated_zone.concert_id)
    return updated_zone
