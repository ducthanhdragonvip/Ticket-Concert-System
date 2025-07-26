from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.orm import relationship
from src.utils.database import Base
from src.entities import TimestampMixin


class Concert(Base,TimestampMixin):
    __tablename__ = "concerts"

    id = Column(String(50), primary_key=True)
    venue_id = Column(String(50), ForeignKey("venues.id"), nullable=False)
    name = Column(String(255), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    num_zones = Column(Integer, nullable=False)
    description = Column(Text)
    location = Column(String(255))

    # Relationships
    venue = relationship("Venue", back_populates="concerts")
    zones = relationship("Zone", back_populates="concert", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Concert(concert_id='{self.concert_id}', name='{self.name}')>"