from datetime import datetime
from src.dto import BaseSchema
from pydantic import BaseModel, validator

class TicketBase(BaseSchema):
    concert_id: str
    zone_id: str
    status: str

    @validator('status')
    def validate_status(cls, v):
        if v not in ['available', 'reserved', 'sold']:
            raise ValueError('Invalid ticket status')
        return v

class TicketCreate(TicketBase):
    pass

class TicketUpdate(TicketBase):
    status: str | None = None

class Ticket(TicketBase):
    id: str
    created_at: datetime
