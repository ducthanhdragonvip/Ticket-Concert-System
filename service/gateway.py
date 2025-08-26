import jwt
import httpx
from urllib.parse import unquote
import asyncio
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import logging_loki
from contextlib import asynccontextmanager

from fastapi_keycloak_middleware.schemas.keycloak_configuration import KeycloakConfiguration
from fastapi_keycloak_middleware import AuthorizationMethod, setup_keycloak_middleware, get_user

from src.utils.observablity import PrometheusMiddleware, metrics, setting_otlp

loki_handler = logging_loki.LokiHandler(
    url="http://localhost:3100/loki/api/v1/push",
    tags={"application": "gateway_service", "environment": "development", "job_name": "gateway_service"},
    version="1",
)

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

root_logger = logging.getLogger(__name__)
root_logger.setLevel(logging.INFO)
root_logger.addHandler(loki_handler)

# Create your application logger
logger = logging.getLogger(__name__)

SERVICES = {
    "admin": "http://127.0.0.1:8003",
    "ticket_ordering": "http://127.0.0.1:8001",
    "data": "http://127.0.0.1:8002"
}


# Global HTTP client
http_client = None

keycloak_config = KeycloakConfiguration(
    realm="ticket_system",
    url="http://localhost:8181",
    client_id="api-gateway",
    client_secret="2TNZtRQWrqv2uqY2JlBZOIHeGkid1Pfe",
    swagger_client_id="api-gateway",
    claims=["sub", "preferred_username", "realm_access"],
    authorization_method=AuthorizationMethod.CLAIM,
    authorization_claim="realm_access",

)

setup_keycloak_middleware(
    app,
    keycloak_configuration=keycloak_config,
    add_swagger_auth=True,
    exclude_patterns=["/", "/health", "/metrics"],
    swagger_auth_pkce=True,

)

setting_otlp(app=app, app_name="gateway_service",endpoint="http://localhost:4317")

app.add_middleware(PrometheusMiddleware, app_name="gateway_service")
app.add_route("/metrics", metrics)

@app.get("/")
def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "Concert Ticketing API Gateway", "services": list(SERVICES.keys())}


async def proxy_request_handler(service_name: str, path: str, request: Request):
    decoded_path = unquote(path)

    auth_header = request.headers.get("Authorization")
    logger.info(f"Processing {request.method} request to {service_name}/{decoded_path}")

    try:
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.error("No valid Authorization header found")
            raise HTTPException(status_code=401, detail="Unauthorized")

        token = auth_header.split(" ")[1]

        # Decode JWT without verification
        decoded_token = jwt.decode(token, options={"verify_signature": False})

        # Extract user information and roles
        username = decoded_token.get("preferred_username", "unknown")
        realm_access = decoded_token.get("realm_access", {})
        user_roles = realm_access.get("roles", [])

        logger.info(f"User {username} with roles: {user_roles}")

        # Authorization based on service and user roles
        if service_name == "admin":
            if "admin" not in user_roles:
                logger.warning(
                    f"User {username} with roles {user_roles} tried to access admin service.")
                raise HTTPException(status_code=403, detail="Forbidden: Admin role required.")

        elif service_name in ["data", "ticket_ordering"]:
            if "user" not in user_roles and "admin" not in user_roles:
                logger.warning(
                    f"User {username} with roles {user_roles} tried to access user/data service.")
                raise HTTPException(status_code=403, detail="Forbidden: User or Admin role required.")

        elif service_name not in SERVICES:
            raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")

    except jwt.DecodeError as e:
        logger.error(f"Failed to decode JWT token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token format")
    except KeyError as e:
        logger.error(f"Missing required field in token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token structure")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process authorization: {e}")
        raise HTTPException(status_code=401, detail="Authorization failed")

    # Proxy logic
    service_url = SERVICES[service_name]
    target_url = f"{service_url}/{decoded_path}"
    query_params = str(request.url.query) if request.url.query else ""
    if query_params:
        target_url += f"?{query_params}"

    try:
        body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()

        response = await http_client.request(
            method=request.method,
            url=target_url,
            headers={k: v for k, v in request.headers.items()
                     if k.lower() not in ['host', 'content-length']},
            content=body,
        )
        logger.info(f"Proxying {request.method} request to {service_name} at {target_url}")

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

# Define separate endpoints for each HTTP method
@app.get("/{service_name}/{path:path}")
async def proxy_get(service_name: str, path: str, request: Request):
    return await proxy_request_handler(service_name, path, request)


@app.post("/{service_name}/{path:path}")
async def proxy_post(service_name: str, path: str, request: Request):
    return await proxy_request_handler(service_name, path, request)


@app.put("/{service_name}/{path:path}")
async def proxy_put(service_name: str, path: str, request: Request):
    return await proxy_request_handler(service_name, path, request)


@app.delete("/{service_name}/{path:path}")
async def proxy_delete(service_name: str, path: str, request: Request):
    return await proxy_request_handler(service_name, path, request)


@app.patch("/{service_name}/{path:path}")
async def proxy_patch(service_name: str, path: str, request: Request):
    return await proxy_request_handler(service_name, path, request)


# this just to debug user info from token which i can't get_user ??
# @app.get("/me")
# async def me(request: Request):
#     try:
#         user = await get_user(request)
#         if user is None:
#             # print(request.scope)
#             print(request.state)
#             logger.error("No user found in request")
#             raise HTTPException(status_code=401, detail="Unauthorized")
#         user_roles = user.realm_access.roles
#         logger.info(f"User {user.preferred_username} with roles: {user_roles}")
#         return {"user": user.dict()}  # Return user details for verification
#     except Exception as e:
#         logger.error(f"Failed to get user: {e}")
#         raise HTTPException(status_code=401, detail="Invalid user information")

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