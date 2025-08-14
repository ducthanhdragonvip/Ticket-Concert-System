from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from src.utils.database import get_db, Base, engine, db_session_context
from src.repositories.concert_repository import concert_repository
from src.repositories.venue_repository import venue_repository
from src.repositories.zone_repository import zone_repository
from src.repositories.ticket_repository import ticket_repository
from src.dto import (
    venue as venue_schemas,
    concert as concert_schemas,
    zone as zone_schemas,
    ticket as ticket_schemas
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Service")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Data Service"}

# Read-only venue endpoints
@app.get("/venues/{venue_id}", response_model=venue_schemas.Venue)
async def read_venue(venue_id: str, db: Session = Depends(get_db)):
    db_session_context.set(db)
    venue = await venue_repository.get(venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue

# Read-only concert endpoints
@app.get("/concerts/{concert_id}", response_model=concert_schemas.ConcertDetail)
async def read_concert(concert_id: str, db: Session = Depends(get_db)):
    db_session_context.set(db)
    concert = await concert_repository.get(concert_id)
    if not concert:
        raise HTTPException(status_code=404, detail="Concert not found")
    return concert

# Read-only zone endpoints
@app.get("/zones/{zone_id}", response_model=zone_schemas.Zone)
async def read_zone(zone_id: str, db: Session = Depends(get_db)):
    db_session_context.set(db)
    zone = await zone_repository.get(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone

# Read-only ticket endpoints
@app.get("/tickets/{ticket_id}", response_model=ticket_schemas.TicketDetail)
async def read_ticket(ticket_id: str, db: Session = Depends(get_db)):
    db_session_context.set(db)
    ticket = await ticket_repository.get_with_details(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket

@app.get("/tickets/concert/{concert_id}", response_model=list[ticket_schemas.Ticket])
async def read_tickets_by_concert(concert_id: str, db: Session = Depends(get_db)):
    db_session_context.set(db)
    tickets = await ticket_repository.get_by_concert(concert_id=concert_id)
    if not tickets:
        raise HTTPException(status_code=404, detail="No tickets found for this concert")
    return tickets

@app.get("/tickets/zone/{zone_id}", response_model=list[ticket_schemas.Ticket])
async def read_tickets_by_zone(zone_id: str, db: Session = Depends(get_db)):
    db_session_context.set(db)
    tickets = await ticket_repository.get_by_zone(zone_id=zone_id)
    if not tickets:
        raise HTTPException(status_code=404, detail="No tickets found for this zone")
    return tickets

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)