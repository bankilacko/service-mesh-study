import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
import psycopg
from fastapi import FastAPI, HTTPException, Request


logger = logging.getLogger("db-service")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "service_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

DB_CONNECT_TIMEOUT = 2

CPU_SERVICE_URL = "http://cpu-service:8000"

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
    title="DB Service",
    lifespan=lifespan,
)


def get_connection():
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=DB_CONNECT_TIMEOUT,
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
    # Liveness check:
    # csak azt ellenorzi, hogy az alkalmazas mukodik-e.
    # Nem fugg a PostgreSQL elerhetosegetol.
    return {"status": "ok"}


@app.get("/ready")
def ready():
    # Readiness check:
    # ellenorzi, hogy az alkalmazas kepes-e
    # PostgreSQL-lekerdezest kiszolgalni.
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

        return {
            "status": "ready",
            "database": "ok",
        }

    except psycopg.Error as exc:
        logger.warning(
            "Database readiness check failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from exc


@app.get("/query")
def query():
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, name FROM items ORDER BY id LIMIT 10"
                )

                rows = cursor.fetchall()

    except psycopg.OperationalError as exc:
        logger.warning(
            "Database query connection failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable",
        ) from exc

    return {
        "service": "db-service",
        "items": [
            {
                "id": row[0],
                "name": row[1],
            }
            for row in rows
        ],
    }


@app.get("/chain/cpu")
async def chain_cpu(request: Request):
    client = request.app.state.http_client

    data = await get_upstream_json(
        client,
        f"{CPU_SERVICE_URL}/compute",
        "CPU Service",
    )

    return {
        "service": "db-service",
        "chain": [
            "db-service",
            "cpu-service",
        ],
        "status": "ok",
        "response": data,
    }