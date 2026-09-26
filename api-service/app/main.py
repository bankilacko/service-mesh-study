from fastapi import FastAPI
import httpx

app = FastAPI(title="API Service")


CPU_SERVICE_URL = "http://cpu-service:8000"
DB_SERVICE_URL = "http://db-service:8000"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/cpu")
async def call_cpu_service():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{CPU_SERVICE_URL}/compute")
        response.raise_for_status()

    return {
        "service": "api-service",
        "response": response.json(),
    }


@app.get("/db")
async def call_db_service():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{DB_SERVICE_URL}/query")
        response.raise_for_status()

    return {
        "service": "api-service",
        "response": response.json(),
    }