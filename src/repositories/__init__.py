from typing import TypeVar, Generic, Any
from sqlalchemy.orm import Session
from src.cache import cache_data
ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")

class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: type[ModelType], id_field: str = "id"):
        self.model = model
        self.id_field = id_field


    @cache_data(key_prefix="entity", expire_time=3600)
    async def get(self, db: Session, id: Any) -> ModelType | None:
        return db.query(self.model).filter(getattr(self.model, self.id_field) == id).first()

    def create(self, db: Session, obj_in: CreateSchemaType) -> ModelType:
        db_obj = self.model(**obj_in.model_dump())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self, db: Session, db_obj: ModelType, obj_in: UpdateSchemaType | dict[str, Any]
    ) -> ModelType:
        obj_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        for field in obj_data:
            setattr(db_obj, field, obj_data[field])
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, id: Any) -> ModelType:
        obj = db.query(self.model).get(id)
        db.delete(obj)
        db.commit()
        return obj

from .venue_repository import venue_repository
from .concert_repository import concert_repository
from .zone_repository import zone_repository
from .ticket_repository import ticket_repository