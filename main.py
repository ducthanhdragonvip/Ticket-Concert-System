import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from src.api.main_router import router as main_router

import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from src.kafka.consumer import ticket_result_consumer
    consumer_task = asyncio.create_task(ticket_result_consumer.start_consuming())
    logger.info("API consumer services initialized")
    yield

    ticket_result_consumer.running = False
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await ticket_result_consumer.cleanup()
    logger.info("Consumer services shut down")

app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Concert Ticketing API"}

app.include_router(main_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)