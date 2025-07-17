from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base
from datetime import datetime


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(String(50), primary_key=True)
    concert_id = Column(String(50), ForeignKey("concerts.id"), nullable=False)
    zone_id = Column(String(50), ForeignKey("zones.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), nullable=False, default="active")

    # Relationships
    concert = relationship("Concert", back_populates="tickets")
    zone = relationship("Zone", back_populates="tickets")

    def __repr__(self):
        return f"<Ticket(ticket_id='{self.ticket_id}', status='{self.status}')>"