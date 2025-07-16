from src.dto import BaseSchema

class ZoneCreate(BaseSchema):
    concert_id: str
    name: str
    price: int
    zone_capacity: int
    available_seats: int
    description: str

class ZoneUpdate(BaseSchema):
    name: str | None = None
    price: int | None = None
    zone_capacity: int | None = None
    available_seats: int | None = None
    description: str | None = None

class Zone(BaseSchema):
    zone_id: str
    concert_id: str
    name: str
    price: int
    zone_capacity: int
    available_seats: int
    description: str