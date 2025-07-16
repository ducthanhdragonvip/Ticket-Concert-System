from sqlalchemy.orm import Session
from src.entities.ticket import Ticket
from src.dto.ticket import TicketCreate, TicketUpdate
from src.repositories import BaseRepository
from datetime import datetime
from uuid import uuid4
from fastapi import HTTPException


class TicketRepository(BaseRepository[Ticket, TicketCreate, TicketUpdate]):
    def __init__(self):
        super().__init__(Ticket, id_field="ticket_id")

    def create(self, db: Session, obj_in: TicketCreate) -> Ticket:
        # First check if zone exists and has available seats
        from src.repositories.zone_repository import zone_repository
        zone = zone_repository.get(db, obj_in.zone_id)

        if not zone:
            raise HTTPException(status_code=404, detail="Zone not found")

        if zone.available_seats <= 0:
            raise HTTPException(status_code=400, detail="No available seats in this zone")

        # Create the ticket
        db_obj = Ticket(
            ticket_id=str(uuid4()),
            concert_id=obj_in.concert_id,
            zone_id=obj_in.zone_id,
            created_at=datetime.now(),
            status=obj_in.status
        )
        db.add(db_obj)

        # Decrement available seats
        zone.available_seats -= 1
        db.add(zone)

        try:
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    def get_by_concert(self, db: Session, concert_id: str) -> list[Ticket]:
        return db.query(self.model).filter(self.model.concert_id == concert_id).all()

    def get_by_zone(self, db: Session, zone_id: str) -> list[Ticket]:
        return db.query(self.model).filter(self.model.zone_id == zone_id).all()

    def get_by_status(self, db: Session, status: str) -> list[Ticket]:
        return db.query(self.model).filter(self.model.status == status).all()

ticket_repository = TicketRepository()