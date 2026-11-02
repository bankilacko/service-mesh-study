import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request


logger = logging.getLogger("api-service")

CPU_SERVICE_URL = "http://cpu-service:8000"
DB_SERVICE_URL = "http://db-service:8000"

HTTP_TIMEOUT = httpx.Timeout(
    10.0,
    connect=2.0,
)

HTTP_LIMITS = httpx.Limits(
    max_connections=100,
    max_keepalive_connections=20,
    keepalive_expiry=30.0,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT,
        limits=HTTP_LIMITS,
    ) as client:
        app.state.http_client = client
        yield


app = FastAPI(
    title="API Service",
    lifespan=lifespan,
)


async def get_upstream_json(
    client: httpx.AsyncClient,
    url: str,
    service_name: str,
) -> Any:
    try:
        response = await client.get(url)
        response.raise_for_status()

        return response.json()

    except httpx.HTTPStatusError as exc:
        logger.warning(
            "%s returned HTTP %s for %s",
            service_name,
            exc.response.status_code,
            url,
        )

        raise HTTPException(
            status_code=502,
            detail=f"{service_name} returned HTTP {exc.response.status_code}",
        ) from exc

    except httpx.RequestError as exc:
        logger.warning(
            "Request to %s failed: %s",
            service_name,
            exc,
        )

        raise HTTPException(
            status_code=502,
            detail=f"{service_name} is unavailable",
        ) from exc

    except ValueError as exc:
        logger.warning(
            "%s returned invalid JSON",
            service_name,
        )

        raise HTTPException(
            status_code=502,
            detail=f"{service_name} returned invalid JSON",
        ) from exc


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/cpu")
async def call_cpu_service(request: Request):
    client = request.app.state.http_client

    data = await get_upstream_json(
        client,
        f"{CPU_SERVICE_URL}/compute",
        "CPU Service",
    )

    return {
        "service": "api-service",
        "response": data,
    }


@app.get("/db")
async def call_db_service(request: Request):
    client = request.app.state.http_client

    data = await get_upstream_json(
        client,
        f"{DB_SERVICE_URL}/query",
        "DB Service",
    )

    return {
        "service": "api-service",
        "response": data,
    }


@app.get("/chain/cpu")
async def chain_cpu(request: Request):
    client = request.app.state.http_client

    data = await get_upstream_json(
        client,
        f"{CPU_SERVICE_URL}/chain/db",
        "CPU Service",
    )

    return {
        "service": "api-service",
        "chain": [
            "api-service",
            "cpu-service",
            "db-service",
            "postgres",
        ],
        "status": "ok",
        "response": data,
    }


@app.get("/chain/db")
async def chain_db(request: Request):
    client = request.app.state.http_client

    data = await get_upstream_json(
        client,
        f"{DB_SERVICE_URL}/chain/cpu",
        "DB Service",
    )

    return {
        "service": "api-service",
        "chain": [
            "api-service",
            "db-service",
            "cpu-service",
        ],
        "status": "ok",
        "response": data,
    }