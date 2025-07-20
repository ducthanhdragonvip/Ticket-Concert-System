from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import relationship
from src.database import Base
from src.entities import TimestampMixin

class Venue(Base,TimestampMixin):
    __tablename__ = "venues"

    id = Column(String(50), primary_key=True, index=True, nullable=False)
    venue_name = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    venues_capacity = Column(Integer, nullable=False)

    # Relationships
    concerts = relationship("Concert", back_populates="venue")

    def __repr__(self):
        return f"<Venue(venue_id='{self.venue_id}', name='{self.venue_name}')>"