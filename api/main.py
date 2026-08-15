import json
import logging
import os
from decimal import Decimal
from typing import Any

import redis
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


load_dotenv()

logger = logging.getLogger(__name__)

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "frauddb")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "10"))
DASHBOARD_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DASHBOARD_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

DATABASE_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
    f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
    socket_timeout=1,
    socket_connect_timeout=1,
)

app = FastAPI(
    title="Fraud Risk Platform API",
    version="1.0.0",
    description="Operational analytics API for streaming account-takeover and fraud-risk signals.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=DASHBOARD_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def make_json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [make_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: make_json_safe(v) for k, v in value.items()}
    return value


def get_cached_or_query(
    cache_key: str,
    sql: str,
    params: dict[str, Any] | None = None,
    ttl: int = CACHE_TTL_SECONDS,
) -> list[dict[str, Any]]:
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except redis.RedisError as exc:
        logger.warning("Redis read failed for %s: %s", cache_key, exc)

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params or {}).mappings().all()
            result = [dict(row) for row in rows]
    except SQLAlchemyError as exc:
        logger.exception("Database query failed for %s", cache_key)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fraud analytics database is unavailable",
        ) from exc

    result = make_json_safe(result)

    try:
        redis_client.setex(cache_key, ttl, json.dumps(result))
    except redis.RedisError as exc:
        logger.warning("Redis write failed for %s: %s", cache_key, exc)

    return result


@app.get("/")
def root():
    return {"message": "Fraud Risk Platform API is running", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "fraud-risk-api"}


@app.get("/ready")
def readiness():
    checks = {"database": False, "redis": False}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = True
    except SQLAlchemyError as exc:
        logger.warning("Readiness database check failed: %s", exc)

    try:
        checks["redis"] = bool(redis_client.ping())
    except redis.RedisError as exc:
        logger.warning("Readiness Redis check failed: %s", exc)

    if not checks["database"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unavailable", "checks": checks},
        )

    status_value = "ready" if checks["redis"] else "degraded"
    return {"status": status_value, "checks": checks}


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
        ttl=5,
    )


@app.get("/raw-events")
def get_raw_events(limit: int = Query(default=20, ge=1, le=200)):
    return get_cached_or_query(
        f"raw_events_{limit}",
        """
        SELECT *
        FROM raw_events_stream
        ORDER BY timestamp DESC
        LIMIT :limit
        """,
        {"limit": limit},
        ttl=5,
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
def user_raw_events(user_id: str, limit: int = Query(default=20, ge=1, le=200)):
    return get_cached_or_query(
        f"user_events_{user_id}_{limit}",
        """
        SELECT *
        FROM raw_events_stream
        WHERE user_id = :user_id
        ORDER BY timestamp DESC
        LIMIT :limit
        """,
        {"user_id": user_id, "limit": limit},
    )


@app.get("/stats/top-users")
def top_users(limit: int = Query(default=10, ge=1, le=100)):
    return get_cached_or_query(
        f"top_users_{limit}",
        """
        SELECT *
        FROM user_risk_summary_stream
        ORDER BY risk_score DESC
        LIMIT :limit
        """,
        {"limit": limit},
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
