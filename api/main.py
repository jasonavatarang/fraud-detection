import os
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
app = FastAPI(title="Fraud Risk Platform")


@app.get("/")
def root():
    return {"message": "Fraud Risk Platform API is running"}


@app.get("/users")
def get_users():
    query = text("""
        SELECT user_id, failed_login_count, has_password_reset,
               has_withdrawal, has_mfa_disabled, has_large_withdrawal,
               total_amount, risk_score, risk_level
        FROM user_risk_summary
        ORDER BY risk_score DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [dict(row) for row in rows]


@app.get("/alerts")
def get_alerts():
    query = text("""
        SELECT user_id, failed_login_count, has_password_reset,
               has_withdrawal, has_mfa_disabled, has_large_withdrawal,
               total_amount, risk_score, risk_level
        FROM alert_users
        ORDER BY risk_score DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [dict(row) for row in rows]


@app.get("/users/{user_id}")
def get_user(user_id: str):
    query = text("""
        SELECT user_id, failed_login_count, has_password_reset,
               has_withdrawal, has_mfa_disabled, has_large_withdrawal,
               total_amount, risk_score, risk_level
        FROM user_risk_summary
        WHERE user_id = :user_id
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"user_id": user_id}).mappings().first()
    return dict(row) if row else {"message": "User not found"}