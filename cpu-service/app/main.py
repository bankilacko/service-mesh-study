from fastapi import FastAPI, Query

app = FastAPI(title="CPU Service")


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