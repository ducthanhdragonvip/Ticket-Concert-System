from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.utils.database import get_db, Base, engine, db_session_context
from src.repositories.ticket_repository import ticket_repository
from src.dto import ticket as ticket_schemas
import logging

router = APIRouter(prefix="/tickets", tags=["tickets"])

logger = logging.getLogger(__name__)

# Ticket endpoints
@router.post("/", response_model=ticket_schemas.TicketDetail)
async def create_ticket(ticket: ticket_schemas.TicketCreate, db: Session = Depends(get_db)):
    db_session_context.set(db)
    try:
        result = await ticket_repository.create(ticket)
        logger.info(f"Ticket created with id {result.id}")
        return result
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            logger.error(f"ValueError creating ticket: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
    except TimeoutError as e:
        logger.error(f"TimeoutError creating ticket: {e}")
        raise HTTPException(status_code=408, detail=str(e))
    except RuntimeError as e:
        logger.error(f"RuntimeError creating ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating ticket: {e}")
        raise HTTPException(status_code=500, detail="Failed to create ticket")

@router.get("/{ticket_id}", response_model=ticket_schemas.TicketDetail)
async def read_ticket(ticket_id: str, db: Session = Depends(get_db)):
    db_session_context.set(db)
    ticket = await ticket_repository.get_with_details(ticket_id)
    if not ticket:
        logger.error("Ticket not found")
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket

@router.get("/concert/{concert_id}", response_model=list[ticket_schemas.Ticket])
async def read_tickets_by_concert(concert_id: str, db: Session = Depends(get_db)):
    db_session_context.set(db)
    tickets = await ticket_repository.get_by_concert(concert_id=concert_id)
    if not tickets:
        logger.error("No tickets found for this concert")
        raise HTTPException(status_code=404, detail="No tickets found for this concert")
    return tickets

@router.get("/zone/{zone_id}", response_model=list[ticket_schemas.Ticket])
async def read_tickets_by_zone(zone_id: str, db: Session = Depends(get_db)):
    db_session_context.set(db)
    tickets = await ticket_repository.get_by_zone(zone_id=zone_id)
    if not tickets:
        logger.error("No tickets found for this zone")
        raise HTTPException(status_code=404, detail="No tickets found for this zone")
    return tickets

