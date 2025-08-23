from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.utils.database import get_db, Base, engine, db_session_context
from src.repositories.concert_repository import concert_repository
from src.dto import concert as concert_schemas
import logging

router = APIRouter(prefix="/concerts", tags=["concerts"])

logger = logging.getLogger(__name__)

# Concert endpoints
@router.post("/", response_model=concert_schemas.Concert)
async def create_concert(concert: concert_schemas.ConcertCreate, db: Session = Depends(get_db)):
    db_session_context.set(db)
    try:
        result = await concert_repository.create(concert)
        logger.info(f"Concert created with id {result.id}")
        return result
    except Exception as e:
        logger.error(f"Error creating concert: {e}")
        raise HTTPException(status_code=500, detail="Failed to create concert")

@router.get("/{concert_id}", response_model=concert_schemas.ConcertDetail)
async def read_concert(concert_id: str, db: Session = Depends(get_db)):
    db_session_context.set(db)
    concert = await concert_repository.get(concert_id)
    if not concert:
        logger.error("Concert not found")
        raise HTTPException(status_code=404, detail="Concert not found")
    return concert

@router.put("/{concert_id}", response_model=concert_schemas.Concert)
async def update_concert(concert_id: str, concert: concert_schemas.ConcertUpdate, db: Session = Depends(get_db)):
    db_session_context.set(db)
    existing_concert = await concert_repository.get(concert_id)
    if not existing_concert:
        logger.error("Concert not found for update")
        raise HTTPException(status_code=404, detail="Concert not found")
    updated_concert = await concert_repository.update(concert_id, concert)
    if not updated_concert:
        logger.error("Failed to update concert")
        raise HTTPException(status_code=500, detail="Failed to update concert")
    return updated_concert
