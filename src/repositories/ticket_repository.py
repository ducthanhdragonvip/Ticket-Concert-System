from sqlalchemy.orm import Session
from src.entities.ticket import Ticket
from src.dto.ticket import TicketCreate, TicketUpdate
from src.repositories import BaseRepository
from src.cache import cache_data, update_cache
from datetime import datetime
from uuid import uuid4
from fastapi import HTTPException


class TicketRepository(BaseRepository[Ticket, TicketCreate, TicketUpdate]):
    def __init__(self):
        super().__init__(Ticket)

    @cache_data(expire_time=3600, use_result_id=True)
    async def create(self, db: Session, obj_in: TicketCreate) -> Ticket:
        # First check if zone exists and has available seats
        from src.repositories.zone_repository import zone_repository
        zone = await zone_repository.get(db, obj_in.zone_id)

        if not zone:
            raise HTTPException(status_code=404, detail="Zone not found")

        if zone.available_seats <= 0:
            raise HTTPException(status_code=400, detail="No available seats in this zone")

        # Create the ticket
        db_obj = Ticket(
            id=str(uuid4()),
            concert_id=obj_in.concert_id,
            zone_id=obj_in.zone_id,
            created_at=datetime.now(),
            status=obj_in.status
        )
        db.add(db_obj)

        # Decrement available seats
        zone = db.merge(zone)
        zone.available_seats -= 1

        try:
            db.commit()
            db.refresh(db_obj)
            db.refresh(zone)

            update_cache(obj_in.zone_id, zone)
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