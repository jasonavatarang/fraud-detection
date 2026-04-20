
# Fraud Risk Streaming Platform

A streaming fraud analytics system built with Kafka, Spark Structured Streaming, PostgreSQL, FastAPI, Redis, and React.

## Overview

This project simulates account activity events, processes them as a live stream, computes user-level fraud risk, stores both raw and summarized data, and exposes operational analytics through APIs and a dashboard.

## Why I built this

I wanted to build a project that demonstrates real event driven system design rather than a simple CRUD application. The project focuses on ingestion, streaming processing, feature engineering, storage design, and API serving.

## How to Run

### Prerequisites

- Docker + Docker Desktop
- Node.js (v18+)
- npm

---

### Start backend services
```
docker compose up --build
```
```
http://localhost:8000/docs
```
* stopping system
```
docker compose down -v
```

### frontend dashboard
```
cd fraud-dashboard
npm install
npm run dev
```
```
http://localhost:5173
```



## Architecture

**Flow:**

Event Producer → Kafka → Spark Structured Streaming → PostgreSQL → FastAPI → Redis → React Dashboard

**Storage Layers:**

- `raw_events_stream` (append-only)
- `user_risk_summary_stream` (upserted)

```text
                ┌──────────────────────┐
                │   Random Producer    │
                │  (simulated events)  │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │        Kafka         │
                │   topic: fraud-events│
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ Spark Structured     │
                │ Streaming            │
                │ (micro-batch engine) │
                └──────────┬───────────┘
                           │
          ┌────────────────┴────────────────┐
          │                                 │
          ▼                                 ▼
┌──────────────────────┐         ┌────────────────────────┐
│ raw_events_stream    │         │ user_risk_summary      │
│ append-only table    │         │ upserted summary table │
│ full event history   │         │ one row per user       │
└──────────┬───────────┘         └──────────┬─────────────┘
           │                                 │
           └────────────────┬────────────────┘
                            ▼
                 ┌──────────────────────┐
                 │      PostgreSQL      │
                 │ source of truth      │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │       FastAPI        │
                 │  read/query layer    │
                 └──────────┬───────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
   ┌──────────────────────┐    ┌──────────────────────┐
   │        Redis         │    │      Dashboard       │
   │ hot endpoint cache   │    │ alerts/stats/users   │
   └──────────────────────┘    └──────────────────────┘


```
---

[image of dashboard]{image\dash_pic.pdf}

## Core Concepts

### Event-driven architecture
The system is built around continuous event ingestion instead of request-response flows.

### Streaming vs batch
- **Batch:** process fixed data once  
- **Streaming:** continuously process incoming events  

This system uses Spark Structured Streaming to process events in micro-batches.

---

## Storage Design

### Raw Event Table (append-only)

`raw_events_stream`

- stores every incoming event  
- no updates or deletes  
- acts as system-of-record  

**Why append-only?**
- preserves history  
- enables recomputation  
- simplifies ingestion  
- avoids write conflicts  

---

### User Summary Table (upserted)

`user_risk_summary_stream`

- one row per user  
- updated continuously  
- contains engineered features  

**Why upsert?**
- dashboard needs current state  
- faster queries  
- avoids scanning raw data repeatedly  

---

## Feature Engineering

The system derives fraud-related features such as:

- failed login count  
- password reset activity  
- withdrawal activity  
- large withdrawal detection  
- event velocity  
- suspicious action combinations  
- total transaction amount  

**Example logic:**
- password reset + withdrawal → suspicious  
- many failed logins → suspicious  
- high-value withdrawal → suspicious  

---

## Risk Scoring

A heuristic scoring system combines features into:

- `risk_score` (numeric)  
- `risk_level` (low / medium / high / critical)  

---

## API Layer (FastAPI)

### Core endpoints
- `GET /stream/users`  
- `GET /stream/alerts`  
- `GET /stream/users/{user_id}`  

### Analytics endpoints
- `GET /stats/overview`  
- `GET /stats/top-users`  
- `GET /stats/risk-distribution`  
- `GET /stats/event-types`  

### Raw data endpoints
- `GET /raw-events`  
- `GET /users/{user_id}/raw-events`  

---

## Caching (Redis)

Redis is used to cache expensive queries:

- overview stats  
- top users  
- alerts  

**Why Redis?**
- reduces latency  
- reduces database load  
- improves dashboard responsiveness  

**Design choice:**  
Redis is not the source of truth — PostgreSQL is.

---

## Frontend Dashboard

Built with React + TypeScript.

Displays:
- overview metrics  
- risk distribution  
- event type distribution  
- top risky users  
- active alerts  
- recent raw events  

---

## Key Design Decisions

### Why Kafka?
- decouples producers and consumers  
- models event streams naturally  
- supports scaling  

### Why Spark Structured Streaming?
- unified batch + streaming API  
- expressive transformations  
- micro-batch processing  

### Why separate raw and summary tables?

**Raw:**
- historical truth  
- debugging  
- recomputation  

**Summary:**
- fast queries  
- current state  
- dashboard-friendly  

### Why not compute everything on request?
- scanning raw data is slow  
- precomputed summaries are faster  

### Why Redis?
- caching improves performance  
- reduces repeated computation  

### Why UUID for events?
- guarantees uniqueness  
- avoids duplicate key errors  

---

## Tradeoffs

### Simplicity vs scalability

Current:
- recomputes summaries from raw data  
- simple and correct  

At scale:
- would switch to incremental updates  
- more efficient but more complex  

### Accuracy vs latency

- caching introduces slight staleness  
- significantly improves performance  

---

## What I Learned

- event-driven system design  
- streaming vs batch processing  
- append-only vs upsert storage  
- feature engineering for fraud detection  
- API design for analytics systems  
- caching with Redis  
- debugging distributed systems  

---

## Future Improvements

- rolling time-window fraud detection  
- incremental summary updates  
- alert notifications (Slack/email)  
- authentication  
- cloud deployment  
- monitoring + observability  

---

## Resume Summary

Built a streaming fraud-risk platform using Kafka, Spark Structured Streaming, PostgreSQL, FastAPI, Redis, and React to ingest simulated events, compute fraud features, and serve real-time analytics via APIs and a dashboard.

---

## Interview Questions & Answers

### Why Kafka instead of direct API ingestion?
Kafka decouples producers and consumers and enables scalable, asynchronous event processing.

### What is a Kafka partition?
A partition allows parallel consumption and maintains ordering within that partition.

### What is an offset?
An offset is the position of a message in a partition.

### Why key by user_id?
Ensures events for the same user stay ordered.

### What is streaming vs batch?
Streaming processes continuous data; batch processes static datasets.

### What is a micro-batch?
A small batch of events processed periodically by Spark.

### What does append-only mean?
New data is added, existing data is never modified.

### What does upsert mean?
Insert if new, update if existing.

### Why separate raw and summary tables?
Raw = history  
Summary = current state  

### What would break at scale?
- recomputing full summaries  
- single-node limits  
- inefficient queries  

### How would you scale this?
- partition Kafka  
- incremental updates  
- distributed compute  
- better caching  

### What happens if Redis fails?
System falls back to PostgreSQL.

### What happens with duplicate events?
Unique event IDs prevent duplicates; further deduping could be added.

### Why not just SQL instead of Spark?
Spark simplifies streaming + distributed processing.

### Hardest part?
Coordinating multiple services and ensuring data consistency.

### What would you improve next?
- time-window fraud detection  
- anomaly detection  
- production deployment  

---

## Final Summary

This project demonstrates:

- event-driven architecture  
- streaming data processing  
- fraud feature engineering  
- append-only data modeling  
- upserted serving tables  
- caching strategies  
- full-stack system design  
- recent suspicious burst detection based on short-window activity

It focuses on **systems thinking**, not just using tools.