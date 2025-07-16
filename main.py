from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from src.database import get_db, Base, engine
from src import entities
from src.database import engine

from src.repositories.venue_repository import venue_repository
from src.repositories.concert_repository import concert_repository
from src.repositories.zone_repository import zone_repository
from src.repositories.ticket_repository import ticket_repository

from src.dto import (
    venue as venue_schemas,
    concert as concert_schemas,
    zone as zone_schemas,
    ticket as ticket_schemas
)

Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to the Concert Ticketing API"}

# Venue endpoints
@app.post("/venues/", response_model=venue_schemas.Venue)
def create_venue(venue: venue_schemas.VenueCreate, db: Session = Depends(get_db)):
    return venue_repository.create(db, venue)

@app.get("/venues/{venue_id}", response_model=venue_schemas.Venue)
def read_venue(venue_id: str, db: Session = Depends(get_db)):
    venue = venue_repository.get(db, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue

# Concert endpoints
@app.post("/concerts/", response_model=concert_schemas.Concert)
def create_concert(concert: concert_schemas.ConcertCreate, db: Session = Depends(get_db)):
    return concert_repository.create(db, concert)

@app.get("/concerts/{concert_id}", response_model=concert_schemas.Concert)
def read_concert(concert_id: str, db: Session = Depends(get_db)):
    concert = concert_repository.get(db, concert_id)
    if not concert:
        raise HTTPException(status_code=404, detail="Concert not found")
    return concert

@app.get("/concerts/{concert_id}/detail", response_model=concert_schemas.ConcertDetail)
def read_concert_detail(concert_id: str, db: Session = Depends(get_db)):
    concert = concert_repository.get_detail(db, concert_id)
    if not concert:
        raise HTTPException(status_code=404, detail="Concert not found")
    return concert

# Zone endpoints
@app.post("/zones/", response_model=zone_schemas.Zone)
def create_zone(zone: zone_schemas.ZoneCreate, db: Session = Depends(get_db)):
    return zone_repository.create(db, zone)

@app.get("/zones/{zone_id}", response_model=zone_schemas.Zone)
def read_zone(zone_id: str, db: Session = Depends(get_db)):
    zone = zone_repository.get(db, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone

# Ticket endpoints
@app.post("/tickets/", response_model=ticket_schemas.Ticket)
async def create_ticket(ticket: ticket_schemas.TicketCreate, db: Session = Depends(get_db)):
    try:
        return ticket_repository.create(db, ticket)
    except Exception as e:
        # Log the error
        raise HTTPException(status_code=500, detail="Failed to create ticket")

@app.get("/tickets/{ticket_id}", response_model=ticket_schemas.Ticket)
async def read_ticket(ticket_id: str, db: Session = Depends(get_db)):
    ticket = ticket_repository.get(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)