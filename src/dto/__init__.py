from pydantic import BaseModel
from datetime import datetime

class BaseSchema(BaseModel):
    class Config:
        from_attributes = True