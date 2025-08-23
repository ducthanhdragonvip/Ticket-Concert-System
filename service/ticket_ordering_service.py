import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from src.utils.database import get_db, Base, engine, db_session_context
from src.repositories.ticket_repository import ticket_repository
from src.dto import ticket as ticket_schemas
import logging
import logging_loki
from src.utils.observablity import PrometheusMiddleware, metrics, setting_otlp

loki_handler = logging_loki.LokiHandler(
    url="http://localhost:3100/loki/api/v1/push",
    tags={"application": "ticket_ordering_service", "environment": "development", "job_name": "ticket_ordering_service"},
    version="1",
)

# Configure root logger first
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(loki_handler)

# Create your application logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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

app = FastAPI(title="Ticket Ordering Service", lifespan=lifespan, root_path="/ticket_ordering")

setting_otlp(app=app, app_name="ticket_ordering_service",endpoint="http://localhost:4317")

app.add_middleware(PrometheusMiddleware, app_name="ticket_ordering_service")
app.add_route("/metrics", metrics)

@app.get("/")
def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to the Ticket Ordering Service"}

@app.post("/tickets/", response_model=ticket_schemas.TicketDetail)
async def create_ticket(ticket: ticket_schemas.TicketCreate, db: Session = Depends(get_db)):
    db_session_context.set(db)
    try:
        result = await ticket_repository.create(ticket)
        logger.info(f"Ticket created with id {result.id}")
        return result
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            logger.error(f"ValueError creating ticket: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
    except TimeoutError as e:
        logger.error(f"TimeoutError creating ticket: {e}")
        raise HTTPException(status_code=408, detail=str(e))
    except RuntimeError as e:
        logger.error(f"RuntimeError creating ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating ticket: {e}")
        raise HTTPException(status_code=500, detail="Failed to create ticket")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)