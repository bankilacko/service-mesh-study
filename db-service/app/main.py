import os

import psycopg
from fastapi import FastAPI

app = FastAPI(title="DB Service")


DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "service_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")


def get_connection():
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


@app.get("/health")
async def health():
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

        return {"status": "ok"}

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@app.get("/query")
async def query():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, name FROM items ORDER BY id LIMIT 10"
            )
            rows = cursor.fetchall()

    return {
        "service": "db-service",
        "items": [
            {"id": row[0], "name": row[1]}
            for row in rows
        ],
    }