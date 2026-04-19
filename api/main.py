import os
import json
import redis
from dotenv import load_dotenv
from fastapi import FastAPI
from sqlalchemy import create_engine, text

load_dotenv()

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "frauddb")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

DATABASE_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
    f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

engine = create_engine(DATABASE_URL, future=True)

redis_client = redis.Redis(host="redis", port=6379, decode_responses=True)

app = FastAPI(title="Fraud Risk Platform - Phase 4")


def get_cached_or_query(cache_key, sql, params=None, ttl=10):
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params or {}).mappings().all()
        result = [dict(row) for row in rows]

    redis_client.setex(cache_key, ttl, json.dumps(result))
    return result


@app.get("/")
def root():
    return {"message": "Fraud Risk Platform API is running"}


@app.get("/stream/users")
def get_stream_users():
    return get_cached_or_query(
        "stream_users",
        """
        SELECT *
        FROM user_risk_summary_stream
        ORDER BY risk_score DESC
        """
    )


@app.get("/stream/alerts")
def get_stream_alerts():
    return get_cached_or_query(
        "stream_alerts",
        """
        SELECT *
        FROM user_risk_summary_stream
        WHERE risk_level IN ('high', 'critical')
        ORDER BY risk_score DESC
        """
    )


@app.get("/stream/users/{user_id}")
def get_stream_user(user_id: str):
    return get_cached_or_query(
        f"user_{user_id}",
        """
        SELECT *
        FROM user_risk_summary_stream
        WHERE user_id = :user_id
        """,
        {"user_id": user_id},
        ttl=5
    )


@app.get("/raw-events")
def get_raw_events(limit: int = 20):
    return get_cached_or_query(
        f"raw_events_{limit}",
        f"""
        SELECT *
        FROM raw_events_stream
        ORDER BY timestamp DESC
        LIMIT {limit}
        """,
        ttl=5
    )