from sqlalchemy.orm import Session
from src.entities.zone import Zone
from src.dto.zone import ZoneCreate, ZoneUpdate
from src.repositories import BaseRepository
from src.cache import cache_data

class ZoneRepository(BaseRepository[Zone, ZoneCreate, ZoneUpdate]):
    def __init__(self):
        super().__init__(Zone)

    @cache_data(expire_time=3600, use_result_id=True)
    async def create(self, db: Session, obj_in: ZoneCreate) -> Zone:
        id = getattr(obj_in, 'id', f"zon_{obj_in.concert_id}_{obj_in.name}")
        db_obj = self.model(
            id=id,
            **obj_in.model_dump(exclude={'zone_id'})
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