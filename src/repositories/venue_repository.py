from sqlalchemy.orm import Session
from src.database import db_session_context
from src.entities.venue import Venue
from src.dto.venue import VenueCreate, VenueUpdate
from src.repositories import BaseRepository
from src.cache import cache_data
from uuid import uuid4


class VenueRepository(BaseRepository[Venue, VenueCreate, VenueUpdate]):
    def __init__(self):
        super().__init__(Venue)

    # @cache_data(key_prefix="venue", expire_time=3600)
    # async def get(self, db: Session, id: str) -> Venue | None:
    #     return db.query(self.model).filter(getattr(self.model, self.id) == id).first()

    @cache_data(expire_time=3600 , use_result_id=True)
    async def create(self, obj_in: VenueCreate) -> Venue:
        db = db_session_context.get()
        # Generate a unique ID if not provided
        id = getattr(obj_in, 'id', f"ven_{uuid4().hex[:8]}")
        db_obj = self.model(
            id=id,
            **obj_in.model_dump(exclude={'id'})
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_name(self, db: Session, name: str) -> Venue | None:
        return db.query(self.model).filter(self.model.venue_name == name).first()

    @cache_data(expire_time=3600)
    def get_detail(self, db: Session, venue_id: str):
        # Implement detailed venue query
        return db.query(Venue).filter(Venue.id == venue_id).first()

venue_repository = VenueRepository()