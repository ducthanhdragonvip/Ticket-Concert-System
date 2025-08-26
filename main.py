import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from src.utils.observablity import PrometheusMiddleware, metrics, setting_otlp
from src.api.main_router import router as main_router

import logging
import logging_loki

loki_handler = logging_loki.LokiHandler(
    url="http://localhost:3100/loki/api/v1/push",
    tags={"application": "main", "environment": "development", "job_name": "main"},
    version="1",
)

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

setting_otlp(app=app, app_name="data_service",endpoint="http://localhost:4317")

app.add_middleware(PrometheusMiddleware, app_name="main")
app.add_route("/metrics", metrics)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Concert Ticketing API"}

app.include_router(main_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8100)