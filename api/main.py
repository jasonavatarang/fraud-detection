import os
import json
import redis
from dotenv import load_dotenv
from fastapi import FastAPI
from sqlalchemy import create_engine, text
from fastapi.middleware.cors import CORSMiddleware
from decimal import Decimal

def make_json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [make_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: make_json_safe(v) for k, v in value.items()}
    return value
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_cached_or_query(cache_key, sql, params=None, ttl=10):
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        print(f"Redis read failed for {cache_key}: {e}")

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params or {}).mappings().all()
        result = [dict(row) for row in rows]

    result = make_json_safe(result)

    try:
        redis_client.setex(cache_key, ttl, json.dumps(result))
    except Exception as e:
        print(f"Redis write failed for {cache_key}: {e}")

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

@app.get("/stats/overview")
def stats_overview():
    return get_cached_or_query(
        "stats_overview",
        """
        SELECT
            COUNT(*) AS total_users,
            COALESCE(SUM(event_count), 0) AS total_events,
            COALESCE(SUM(CASE WHEN risk_level IN ('high','critical') THEN 1 ELSE 0 END), 0) AS alerted_users,
            COALESCE(SUM(CASE WHEN risk_level = 'critical' THEN 1 ELSE 0 END), 0) AS critical_users,
            COALESCE(AVG(risk_score), 0) AS avg_risk_score
        FROM user_risk_summary_stream
        """
    )

@app.get("/stats/risk-distribution")
def risk_distribution():
    return get_cached_or_query(
        "risk_distribution",
        """
        SELECT risk_level, COUNT(*) AS count
        FROM user_risk_summary_stream
        GROUP BY risk_level
        ORDER BY count DESC
        """
    )

@app.get("/users/{user_id}/raw-events")
def user_raw_events(user_id: str):
    return get_cached_or_query(
        f"user_events_{user_id}",
        """
        SELECT *
        FROM raw_events_stream
        WHERE user_id = :user_id
        ORDER BY timestamp DESC
        LIMIT 20
        """,
        {"user_id": user_id}
    )



@app.get("/stats/top-users")
def top_users(limit: int = 10):
    return get_cached_or_query(
        f"top_users_{limit}",
        f"""
        SELECT *
        FROM user_risk_summary_stream
        ORDER BY risk_score DESC
        LIMIT {limit}
        """
    )


@app.get("/stats/event-types")
def event_types():
    return get_cached_or_query(
        "event_types",
        """
        SELECT event_type, COUNT(*) AS count
        FROM raw_events_stream
        GROUP BY event_type
        ORDER BY count DESC
        """
    )

@app.get("/stats/recent-bursts")
def recent_bursts():
    return get_cached_or_query(
        "recent_bursts",
        """
        SELECT *
        FROM recent_burst_activity
        WHERE burst_level IN ('medium', 'high')
        ORDER BY burst_score DESC
        """
    )