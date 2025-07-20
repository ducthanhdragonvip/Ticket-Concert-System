from sqlalchemy.orm import Session
from src.database import db_session_context
from src.entities.ticket import Ticket
from src.dto.ticket import TicketCreate, TicketUpdate, TicketDetail
from src.repositories import BaseRepository, concert_repository
from src.cache import cache_data, update_cache
from uuid import uuid4
from fastapi import HTTPException


class TicketRepository(BaseRepository[Ticket, TicketCreate, TicketUpdate]):
    def __init__(self):
        super().__init__(Ticket)

    @cache_data(expire_time=3600, use_result_id=True)
    async def create(self,obj_in: TicketCreate) -> TicketDetail:
        db = db_session_context.get()
        # First check if zone exists and has available seats
        from src.repositories.zone_repository import zone_repository
        zone = await zone_repository.get(db, obj_in.zone_id)

        if not zone:
            raise HTTPException(status_code=404, detail="Zone not found")

        if zone.available_seats <= 0:
            raise HTTPException(status_code=400, detail="No available seats in this zone")

        concert = await concert_repository.get(zone.concert_id)

        # Create the ticket
        db_obj = Ticket(
            id=str(uuid4()),
            zone_id=obj_in.zone_id,
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
            return TicketDetail(
                id=db_obj.id,
                zone_id=db_obj.zone_id,
                status=db_obj.status,
                created_at=db_obj.created_at,
                updated_at=db_obj.updated_at,
                concert_name=concert.name if concert else None,
                concert_description=concert.description if concert else None,
                price=zone.price if zone else None,
                zone_name=zone.name if zone else None,
                zone_description=zone.description if zone else None
            )
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    @cache_data(expire_time=3600)
    async def get_with_details(self, ticket_id: str) -> TicketDetail | None:
        db = db_session_context.get()
        from src.repositories.zone_repository import zone_repository
        from src.repositories.concert_repository import concert_repository

        ticket = await self.get(ticket_id)
        if not ticket:
            return None

        zone = await zone_repository.get(ticket.zone_id)
        concert = None
        if zone:
            concert = await concert_repository.get(zone.concert_id)

        # Create TicketDetail with extracted information
        return TicketDetail(
            id=ticket.id,
            zone_id=ticket.zone_id,
            status=ticket.status,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            concert_name=concert.name if concert else None,
            concert_description=concert.description if concert else None,
            price=zone.price if zone else None,
            zone_name=zone.name if zone else None,
            zone_description=zone.description if zone else None
        )

    def get_by_concert(self, db: Session, concert_id: str) -> list[Ticket]:
        return db.query(self.model).filter(self.model.concert_id == concert_id).all()

    def get_by_zone(self, db: Session, zone_id: str) -> list[Ticket]:
        return db.query(self.model).filter(self.model.zone_id == zone_id).all()

    def get_by_status(self, db: Session, status: str) -> list[Ticket]:
        return db.query(self.model).filter(self.model.status == status).all()

ticket_repository = TicketRepository()