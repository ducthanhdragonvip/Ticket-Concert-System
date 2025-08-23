from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.utils.database import get_db, Base, engine, db_session_context
from src.repositories.venue_repository import venue_repository
from src.dto import venue as venue_schemas
import logging

router = APIRouter(prefix="/venues", tags=["venues"])

logger = logging.getLogger(__name__)

@router.post("/", response_model=venue_schemas.Venue)
async def create_venue(venue: venue_schemas.VenueCreate, db: Session = Depends(get_db)):
    db_session_context.set(db)
    try:
        result = await venue_repository.create(venue)
        logger.info(f"Venue created with id {result.id}")
        return result
    except Exception as e:
        logger.error(f"Error creating venue: {e}")
        raise HTTPException(status_code=500, detail="Failed to create venue")

@router.get("/{venue_id}", response_model=venue_schemas.Venue)
async def read_venue(venue_id: str, db: Session = Depends(get_db)):
    db_session_context.set(db)
    venue = await venue_repository.get(venue_id)
    if not venue:
        logger.error("Venue not found")
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue

@router.put("/{venue_id}", response_model=venue_schemas.Venue)
async def update_venue(venue_id: str, venue: venue_schemas.VenueUpdate, db: Session = Depends(get_db)):
    db_session_context.set(db)
    existing_venue = await venue_repository.get(venue_id)
    if not existing_venue:
        logger.error("Venue not found for update")
        raise HTTPException(status_code=404, detail="Venue not found")
    updated_venue = await venue_repository.update(venue_id, venue)
    if not updated_venue:
        logger.error("Failed to update venue")
        raise HTTPException(status_code=500, detail="Failed to update venue")
    return updated_venue
