from typing import TypeVar, Generic, Any
from src.utils.database import db_session_context
from src.utils.cache import cache_data , update_cache , invalidate_cache
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

    async def update(self, id: Any, obj_in: UpdateSchemaType) -> ModelType | None:
        """
        Update an existing record in the database.
        """
        db = db_session_context.get()
        obj = db.query(self.model).filter(getattr(self.model, self.id) == id).first()

        if not obj:
            return None

        update_data = obj_in.dict(exclude_unset=True) if hasattr(obj_in, 'dict') else obj_in.model_dump(
            exclude_unset=True)

        for key, value in obj_in.dict(exclude_unset=True).items():
            setattr(obj, key, value)
        db.commit()
        db.refresh(obj)

        cache_key = str(id)
        update_cache(cache_key, obj, expire_time=3600)

        return obj


    async def delete(self,id: Any) -> ModelType:
        db = db_session_context.get()
        obj = db.query(self.model).filter(getattr(self.model, self.id) == id).first()
        if not obj:
            return None
        db.delete(obj)
        db.commit()
        invalidate_cache(str(id))
        return obj