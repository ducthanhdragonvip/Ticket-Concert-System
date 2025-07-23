from typing import TypeVar, Generic, Any
from src.utils.database import db_session_context
from src.utils.cache import cache_data
ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")

class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: type[ModelType], id_field: str = "id"):
        self.model = model
        self.id = id_field

    @cache_data(expire_time=3600)
    def get(self, id: Any) -> ModelType | None:
        db = db_session_context.get()
        return db.query(self.model).filter(getattr(self.model, self.id) == id).first()

    async def create(self, obj_in: CreateSchemaType) -> ModelType:
        db = db_session_context.get()
        db_obj = self.model(**obj_in.model_dump())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    async def update(
        self, db_obj: ModelType, obj_in: UpdateSchemaType | dict[str, Any]
    ) -> ModelType:
        db = db_session_context.get()
        obj_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        for field in obj_data:
            setattr(db_obj, field, obj_data[field])
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    async def delete(self,id: Any) -> ModelType:
        db = db_session_context.get()
        obj = db.query(self.model).get(id)
        db.delete(obj)
        db.commit()
        return obj

from .venue_repository import venue_repository
from .concert_repository import concert_repository
from .zone_repository import zone_repository
from .ticket_repository import ticket_repository