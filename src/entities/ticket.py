from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from src.utils.database import Base
from src.entities import TimestampMixin


class Ticket(Base,TimestampMixin):
    __tablename__ = "tickets"

    id = Column(String(50), primary_key=True)
    zone_id = Column(String(50), ForeignKey("zones.id"), nullable=False)
    # status = Column(String(20), nullable=False, default="active")

    # Relationships
    zone = relationship("Zone", back_populates="tickets")

    def __repr__(self):
        return f"<Ticket(ticket_id='{self.ticket_id}', status='{self.status}')>"