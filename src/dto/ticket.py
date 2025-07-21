from datetime import datetime
from src.dto import BaseSchema
from pydantic import BaseModel, validator

class TicketBase(BaseSchema):
    zone_id: str
    # status: str
    #
    # @validator('status')
    # def validate_status(cls, v):
    #     if v not in ['available', 'reserved', 'sold']:
    #         raise ValueError('Invalid ticket status')
    #     return v

class TicketCreate(TicketBase):
    pass

class TicketUpdate(TicketBase):
    zone_id : str | None = None
    # status: str | None = None

class Ticket(TicketBase):
    id: str
    created_at: datetime
    updated_at: datetime

class TicketDetail(Ticket):
    concert_name: str | None = None
    concert_description: str | None = None
    price: float | None = None
    zone_name: str | None = None
    zone_description: str | None = None
