from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from src.utils.database import get_db, Base, engine, db_session_context
from src.repositories.venue_repository import venue_repository
from src.repositories.concert_repository import concert_repository
from src.repositories.zone_repository import zone_repository
from src.repositories.ticket_repository import ticket_repository
from src.utils.cache import invalidate_cache
import logging


from src.dto import (
    venue as venue_schemas,
    concert as concert_schemas,
    zone as zone_schemas,
    ticket as ticket_schemas
)

Base.metadata.create_all(bind=engine)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from src.kafka.consumer import ticket_result_consumer
    ticket_result_consumer.start_consuming()
    logger.info("API consumer services initialized")
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Concert Ticketing API"}

# Venue endpoints
@app.post("/venues/", response_model=venue_schemas.Venue)
async def create_venue(venue: venue_schemas.VenueCreate, db: Session = Depends(get_db)):
    db_session_context.set(db)
    result = await venue_repository.create(venue)
    # Invalidate relevant caches after creation
    return result

@app.get("/venues/{venue_id}", response_model=venue_schemas.Venue)
async def read_venue(venue_id: str, db: Session = Depends(get_db)):
    db_session_context.set(db)
    venue = await venue_repository.get(venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue

# Concert endpoints
@app.post("/concerts/", response_model=concert_schemas.Concert)
async def create_concert(concert: concert_schemas.ConcertCreate, db: Session = Depends(get_db)):
    db_session_context.set(db)
    result = await concert_repository.create(concert)
    return result

@app.get("/concerts/{concert_id}", response_model=concert_schemas.ConcertDetail)
async def read_concert(concert_id: str, db: Session = Depends(get_db)):
    db_session_context.set(db)
    concert = await concert_repository.get(concert_id)
    if not concert:
        raise HTTPException(status_code=404, detail="Concert not found")
    return concert

@app.put("/concerts/{concert_id}", response_model=concert_schemas.Concert)
async def update_concert(concert_id: str, concert: concert_schemas.ConcertUpdate, db: Session = Depends(get_db)):
    db_session_context.set(db)
    existing_concert = await concert_repository.get(concert_id)
    if not existing_concert:
        raise HTTPException(status_code=404, detail="Concert not found")
    updated_concert = await concert_repository.update(concert_id, concert)
    if not updated_concert:
        raise HTTPException(status_code=500, detail="Failed to update concert")
    return updated_concert

# Zone endpoints
@app.post("/zones/", response_model=zone_schemas.Zone)
async def create_zone(zone: zone_schemas.ZoneCreate, db: Session = Depends(get_db)):
    db_session_context.set(db)
    result = await zone_repository.create(zone)
    invalidate_cache(zone.concert_id)
    return result

@app.get("/zones/{zone_id}", response_model=zone_schemas.Zone)
async def read_zone(zone_id: str, db: Session = Depends(get_db)):
    db_session_context.set(db)
    zone = await zone_repository.get(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone

# Ticket endpoints
@app.post("/tickets/", response_model=ticket_schemas.TicketDetail)
async def create_ticket(ticket: ticket_schemas.TicketCreate, db: Session = Depends(get_db)):
    db_session_context.set(db)
    try:
        return await ticket_repository.create(ticket)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating ticket: {e}")
        raise HTTPException(status_code=500, detail="Failed to create ticket")

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
    uvicorn.run(app, host="127.0.0.1", port=8000)