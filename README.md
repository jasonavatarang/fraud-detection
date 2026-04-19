# fraud-detection



# Description
## Possible features

* ingests account acitivy logs
* process them with PySpark
* computes a risk score
* stores resutls in Postgres
* exposes alerts thorugh FastAPI
* possibly add kafk, ml anomaly detection, dashboard

## what system should detect
* login from new IP
* login from new location
* password reset followed by withdrawal
* multiple failed logins
* unusual transaction amount
* device change before trade/transfer
* rapid sequence of sensitive actions

# Core Stack
* Python
* PySpark (reads raw events and computes suspciious patterns) --> user_risk_summary, alert_events
* PostgreSQL
* FastAPI
* Docer Compose
## thinking about
* kafka
* react
* redis
* kubernetes
* redis
* hadoop

# data models
  | Events.csv     | Description |
| ----------- | ----------- |
| event_id     |      |
| user_id  |      |
| event_type  |  login_sucess, login_failed, password_reset, trade, withdrawal, mfa_disabled, profile_change|
| timestamp | ||
|ip_address| ||
|location| ||
|device_id| ||
|amount| ||
|status| ||

# feature logic ideas
## Rule 1
More than 3 failed logins within 1 hour: high risk
## Rule 2
Password reset followed by withdrawal within 30 minutes: critical risk
## Rule 3
MFA disabled before profile change or withdrawal: critical risk
## Rule 4
Login from a new location and a new device: medium/high risk
## Rule 5
Withdrawal over threshold: medium risk (higher if combined with new device/location)

# Phase 1

## overview
This pahse ingests raw account activity events, transforms them into user level risk features, computes a rule based risk score, stores the results in PostgreSQL, and exposes the processed insights through a FastAPI service.

## Architecture
 Raw CSV events flow through a Spark processing job, which computes user risk summaries and alert tables. These are written to PostgreSQL and served through REST endpoints.


```
CSV file
   ↓
Spark (parallel processing)
   ↓ (via JDBC)
Postgres (storage)
   ↓ (via SQLAlchemy)
FastAPI (API layer)
   ↓ (via Uvicorn)
Browser / client
```

## features

- Detect repeated failed login behavior
- Flag password reset and large withdrawal activity
- Compute a user level risk score
- Return high risk users through API endpoints

## Tech stack
- Python, PySpark, PostgreSQL, FastAPI, Docker Compose

## How to run
```
docker compose up --build
```
## endpoints (port 8000)
 - GET /
 - GET /users
 - GET /alerts
 - GET /users/{user_id}
 - /docs 

 # Phase 2

### Fraud / risk features
- repeated failed login detection
- password reset detection
- large withdrawal detection
- MFA disabled detection
- multiple device detection
- multiple location detection
- high event volume detection
- password reset + withdrawal combination flag

### Analytics features
- risk overview summary
- risk distribution across users
- top risky users
- risk/event patterns by location
- event type distribution

## Architecture

```text
Raw CSV Events
    ↓
PySpark Processing / Feature Engineering
    ↓
PostgreSQL Curated Tables
    ↓
FastAPI Endpoints
    ↓
Operational / Analytical Insights

## Core
- GET /
- GET /users
- GET /alerts
- GET /users/{user_id}
## Analytics
- GET /stats/overview
- GET /stats/risk-distribution
- GET /stats/top-users
- GET /stats/by-location
- GET /stats/event-types

 # Phase 3

 - kafka proudcer/consumer
 - stream events instead of CSV-only
 ```
 Producer -> Kafka -> Spark Streaming -> Postgres -> FastAPI
 ```
 ## producers hypothetically
web app -> sends login events
mobile app -> sends trade events
backend -> sends withdrawals

## consumers
Spark → fraud detection
another service → analytics
another service → alerts

# Fraud Risk Platform — Phase 3B

Phase 3B upgrades the project from a batch analytics pipeline into a streaming system that ingests live events from Kafka, processes them with Spark Structured Streaming, writes micro-batch results into PostgreSQL, and serves them through FastAPI.

## What changed from Phase 3A

### Phase 3A
- Kafka producer sends events
- Spark Structured Streaming reads from Kafka
- Results are written to the console

### Phase 3B
- Kafka producer sends events continuously
- Spark Structured Streaming reads from Kafka
- Each micro-batch is processed with `foreachBatch`
- Aggregated fraud summaries and alerts are written to PostgreSQL
- FastAPI reads the streaming-backed tables

## Architecture

```text
Producer -> Kafka -> Spark Structured Streaming -> PostgreSQL -> FastAPI

 # Phase 4
 - Redis caching
 - maybe bakcground jobs
## Phase 4

Phase 4 upgrades the project from a streaming summary pipeline into a more production-like architecture with raw event persistence, summary upserts, and Redis-backed API caching.

### New capabilities
- appends streaming events into a persistent raw event table
- recomputes user-level summaries from raw history
- upserts user risk summaries by `user_id`
- caches hot API responses using Redis

### Updated architecture

Producer -> Kafka -> Spark Structured Streaming -> PostgreSQL (raw + summary) -> FastAPI -> Redis

### Storage model

#### Raw events
`raw_events_stream`
- append-only
- stores all ingested events
- acts as event history / audit trail

#### Summary table
`user_risk_summary_stream`
- one row per user
- updated via Postgres upsert
- supports alert and user lookup endpoints

### API updates
- `GET /stream/users`
- `GET /stream/alerts`
- `GET /stream/users/{user_id}`
- `GET /raw-events`

### Redis role
Redis is used as a cache layer for hot endpoints. PostgreSQL remains the source of truth.

### Why this phase matters
This phase demonstrates:
- append-only event storage
- summary upsert patterns
- separation of raw and curated data
- API caching
- a more realistic streaming data architecture
# Phase 5
- aws deployemnt
- s3 + hosted DB + app deployment

# Phase 6
- kubernetes deployment
- help/ manifest ?
