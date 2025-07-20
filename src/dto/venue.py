from datetime import datetime

from src.dto import BaseSchema

class VenueCreate(BaseSchema):
    venue_name: str
    location: str
    venues_capacity: int

class VenueUpdate(BaseSchema):
    venue_name: str | None = None
    location: str | None = None
    venues_capacity: int | None = None

class Venue(BaseSchema):
    id: str
    venue_name: str
    location: str
    venues_capacity: int
    created_at: datetime
    updated_at: datetime