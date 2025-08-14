import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from src.utils.database import get_db, Base, engine, db_session_context
from src.repositories.ticket_repository import ticket_repository
from src.dto import ticket as ticket_schemas
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from src.kafka.consumer import ticket_result_consumer
    consumer_task = asyncio.create_task(ticket_result_consumer.start_consuming())
    logger.info("Ticket ordering service initialized")
    yield

    ticket_result_consumer.running = False
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await ticket_result_consumer.cleanup()
    logger.info("Ticket ordering service shut down")

app = FastAPI(title="Ticket Ordering Service", lifespan=lifespan)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Ticket Ordering Service"}

@app.post("/tickets/", response_model=ticket_schemas.TicketDetail)
async def create_ticket(ticket: ticket_schemas.TicketCreate, db: Session = Depends(get_db)):
    db_session_context.set(db)
    try:
        return await ticket_repository.create(ticket)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating ticket: {e}")
        raise HTTPException(status_code=500, detail="Failed to create ticket")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)