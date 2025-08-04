from sqlalchemy.orm import Session, joinedload
from src.entities.concert import Concert
from src.dto.concert import ConcertCreate, ConcertUpdate
from src.repositories.base import BaseRepository
from src.utils.cache import cache_data
from src.utils.database import db_session_context
from src.utils.kafka_config import kafka_config
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)


class ConcertRepository(BaseRepository[Concert, ConcertCreate, ConcertUpdate]):
    def __init__(self):
        super().__init__(Concert)

    @cache_data(expire_time=3600, use_result_id=True)
    def create(self, obj_in: ConcertCreate) -> Concert:
        db = db_session_context.get()
        id = getattr(obj_in, 'id', f"con_{uuid4().hex[:8]}")
        db_obj = self.model(
            id=id,
            **obj_in.model_dump(exclude={'id'})
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)

        try:
            kafka_config.create_concert_topics(
                concert_id=id,
                num_partitions=obj_in.num_zones
            )
            logger.info(f"Created Kafka topics for concert {id} with {obj_in.num_zones} partitions")
        except Exception as e:
            logger.error(f"Failed to create Kafka topics for concert {id}: {e}")

        return db_obj

    @cache_data(expire_time=3600)
    def get(self, id: str) -> Concert | None:
        db = db_session_context.get()
        return db.query(self.model).options(joinedload(self.model.zones)).filter(
            getattr(self.model, self.id) == id
        ).first()

    def get_by_venue(self, db: Session, venue_id: str) -> list[Concert]:
        return db.query(self.model).filter(self.model.venue_id == venue_id).all()

    def get_upcoming(self, db: Session) -> list[Concert]:
        from datetime import datetime
        return db.query(self.model).filter(self.model.start_time > datetime.now()).all()

    def get_detail(self, db: Session, concert_id: str) -> Concert:
        """Get a concert by ID with all related zones"""
        return db.query(self.model).filter(getattr(self.model, self.id_field) == concert_id).first()

concert_repository = ConcertRepository()