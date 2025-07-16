from sqlalchemy.orm import Session
from src.entities.venue import Venue
from src.dto.venue import VenueCreate, VenueUpdate
from src.repositories import BaseRepository
from uuid import uuid4


class VenueRepository(BaseRepository[Venue, VenueCreate, VenueUpdate]):
    def __init__(self):
        super().__init__(Venue,id_field="venue_id")

    def create(self, db: Session, obj_in: VenueCreate) -> Venue:
        # Generate a unique ID if not provided
        venue_id = getattr(obj_in, 'venue_id', f"ven_{uuid4().hex[:8]}")
        db_obj = self.model(
            venue_id=venue_id,
            **obj_in.model_dump(exclude={'venue_id'})
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_name(self, db: Session, name: str) -> Venue | None:
        return db.query(self.model).filter(self.model.venue_name == name).first()

venue_repository = VenueRepository()