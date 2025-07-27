from sqlalchemy import func
from sqlalchemy.orm import Session
from src.utils.database import db_session_context
from src.entities.zone import Zone
from src.dto.zone import ZoneCreate, ZoneUpdate
from src.repositories import BaseRepository
from src.repositories.concert_repository import concert_repository
from src.utils.cache import cache_data

from fastapi import HTTPException


class ZoneRepository(BaseRepository[Zone, ZoneCreate, ZoneUpdate]):
    def __init__(self):
        super().__init__(Zone)

    @cache_data(expire_time=3600, use_result_id=True)
    async def create(self, obj_in: ZoneCreate) -> Zone:
        db = db_session_context.get()

        concert = await concert_repository.get(obj_in.concert_id)

        max_zone_number = db.query(func.max(Zone.zone_number)).filter(
            Zone.concert_id == obj_in.concert_id
        ).scalar()

        next_zone_number = (max_zone_number or 0) + 1

        if next_zone_number > concert.num_zones:
            raise HTTPException(detail="Cannot create more zones than the concert's num_zones", status_code=409)

        id = getattr(obj_in, 'id', f"zon_{obj_in.concert_id}_{obj_in.name}_{next_zone_number}")
        db_obj = self.model(
            id=id,
            zone_number=next_zone_number,
            **obj_in.model_dump(exclude={'id'})
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_concert(self, db: Session, concert_id: str) -> list[Zone]:
        return db.query(self.model).filter(self.model.concert_id == concert_id).all()

    def update_available_seats(self, db: Session, zone_id: str, change: int) -> Zone | None:
        zone = self.get(db, zone_id)
        if zone:
            zone.available_seats += change
            db.commit()
            db.refresh(zone)
        return zone

    def update_seats(self, db: Session, zone_id: str, delta: int) -> Zone | None:
        zone = self.get(db, zone_id)
        if not zone:
            return None

        if zone.available_seats + delta < 0:
            raise ValueError("Not enough available seats")

        zone.available_seats += delta
        db.add(zone)
        db.commit()
        db.refresh(zone)
        return zone

zone_repository = ZoneRepository()