from fastapi import FastAPI, Query
import httpx

app = FastAPI(title="CPU Service")

DB_SERVICE_URL = "http://db-service:8000"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/compute")
async def compute(
    iterations: int = Query(default=1_000_000, ge=1)
):
    result = 0

    for i in range(iterations):
        result += (i * i) % 97

    return {
        "service": "cpu-service",
        "iterations": iterations,
        "result": result,
    }


@app.get("/chain/db")
async def chain_db():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{DB_SERVICE_URL}/query")
        response.raise_for_status()

    return {
        "service": "cpu-service",
        "chain": [
            "cpu-service",
            "db-service",
            "postgres",
        ],
        "status": "ok",
        "response": response.json(),
    }