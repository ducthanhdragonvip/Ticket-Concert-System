from datetime import datetime
from src.dto import BaseSchema
from src.dto.zone import Zone as ZoneSchema


class ConcertCreate(BaseSchema):
    venue_id: str
    name: str
    start_time: datetime
    end_time: datetime
    description: str
    location: str

class ConcertUpdate(BaseSchema):
    venue_id: str | None = None
    name: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    description: str | None = None
    location: str | None = None

class Concert(BaseSchema):
    id: str
    venue_id: str
    name: str
    start_time: datetime
    end_time: datetime
    description: str
    location: str

class ConcertDetail(Concert):
    zones: list[ZoneSchema] = []