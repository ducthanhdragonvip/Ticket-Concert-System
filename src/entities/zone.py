from sqlalchemy import Column, String, Integer, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from src.database import Base


class Zone(Base):
    __tablename__ = "zones"

    id = Column(String(50), primary_key=True)
    concert_id = Column(String(50), ForeignKey("concerts.id"), nullable=False)
    name = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)
    zone_capacity = Column(Integer, nullable=False)
    available_seats = Column(Integer, nullable=False)
    description = Column(Text)

    # Relationships
    concert = relationship("Concert", back_populates="zones")
    tickets = relationship("Ticket", back_populates="zone", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Zone(zone_id='{self.zone_id}', name='{self.name}')>"