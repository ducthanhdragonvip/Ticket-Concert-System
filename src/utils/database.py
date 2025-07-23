from contextvars import ContextVar

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from src.utils.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

from src.entities.venue import Venue
from src.entities.concert import Concert
from src.entities.zone import Zone
from src.entities.ticket import Ticket

async def get_db() -> Session :
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_session_context : ContextVar[Session] = ContextVar("db_session_context")