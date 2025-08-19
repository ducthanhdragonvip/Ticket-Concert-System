import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import logging_loki
from contextlib import asynccontextmanager
from typing import Optional
from src.utils.observablity import PrometheusMiddleware, metrics, setting_otlp

loki_handler = logging_loki.LokiHandler(
    url="http://localhost:3100/loki/api/v1/push",
    tags={"application": "gateway_service", "environment": "development", "job_name": "gateway_service"},
    version="1",
)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(loki_handler)

# Create your application logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SERVICES = {
    "admin": "http://127.0.0.1:8003",
    "ticket_ordering": "http://127.0.0.1:8001",
    "data": "http://127.0.0.1:8002"
}

# Global HTTP client
http_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    # Startup - optimized HTTP client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(5.0, connect=2.0),  # Reduced timeouts
        limits=httpx.Limits(
            max_keepalive_connections=50,
            max_connections=200,
            keepalive_expiry=30.0
        ),
        # http2=True  # Enable HTTP/2 for better performance
    )
    logger.info("Gateway initialized with optimized HTTP client")
    yield
    # Shutdown
    await http_client.aclose()
    logger.info("Gateway shut down")


app = FastAPI(title="Concert Ticketing API Gateway", lifespan=lifespan)

setting_otlp(app=app, app_name="gateway_service",endpoint="http://localhost:4317")

app.add_middleware(PrometheusMiddleware, app_name="gateway_service")
app.add_route("/metrics", metrics)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "Concert Ticketing API Gateway", "services": list(SERVICES.keys())}


@app.api_route("/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_request(service_name: str, path: str, request: Request):
    if service_name not in SERVICES:
        logger.error(f"Service '{service_name}' not found")
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")

    service_url = SERVICES[service_name]
    target_url = f"{service_url}/{path}"

    # Get query parameters
    query_params = str(request.url.query) if request.url.query else ""
    if query_params:
        target_url += f"?{query_params}"

    try:
        # Get request body if present
        body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()

        # Forward the request
        response = await http_client.request(
            method=request.method,
            url=target_url,
            headers={k: v for k, v in request.headers.items()
                     if k.lower() not in ['host', 'content-length']},
            content=body,
        )
        logger.info(f"Proxying {request.method} request to {service_name} at {target_url}")
        # Return the response
        return JSONResponse(
            status_code=response.status_code,
            content=response.json() if response.content else None,
            headers={k: v for k, v in response.headers.items()
                     if k.lower() not in ['content-encoding', 'transfer-encoding']}
        )

    except httpx.RequestError as e:
        logger.error(f"Request failed to {service_name}: {e}")
        raise HTTPException(status_code=503, detail=f"Service '{service_name}' unavailable")
    except Exception as e:
        logger.error(f"Unexpected error proxying to {service_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal gateway error")


@app.get("/health")
async def health_check():
    """Check health of all services"""
    health_status = {}

    for service_name, service_url in SERVICES.items():
        try:
            response = await http_client.get(f"{service_url}/", timeout=2.0)
            health_status[service_name] = {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "status_code": response.status_code
            }
        except Exception as e:
            health_status[service_name] = {
                "status": "unhealthy",
                "error": str(e)
            }

    return {"gateway": "healthy", "services": health_status}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)