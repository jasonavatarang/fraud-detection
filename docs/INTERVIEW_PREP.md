# Interview Prep

## 30 Second Pitch

I built a real-time fraud risk streaming platform that simulates account activity, ingests it through Kafka, processes it with Spark Structured Streaming, stores raw events and user summaries in PostgreSQL, serves analytics through FastAPI with Redis caching, and displays suspicious users in a React dashboard. The point was to show how fraud detection works as an operational system, not just as an offline notebook.

I also added a real-data benchmark path: after downloading a labeled Kaggle-style fraud CSV, the repo can profile the data, train a class-weighted baseline model, report ROC-AUC and precision/recall style metrics, and export replayable events for the dashboard.

## Resume Bullets

- Built a real-time fraud risk platform using Kafka, Spark Structured Streaming, PostgreSQL, Redis, FastAPI, and React to monitor account-takeover style activity.
- Implemented explainable fraud-risk features such as failed-login velocity, password-reset plus withdrawal sequences, large withdrawals, MFA-disabled activity, and suspicious recent bursts.
- Added replay-safe event ingestion with `event_id` primary keys and `ON CONFLICT DO NOTHING` handling to avoid duplicate raw events during Kafka replays or checkpoint resets.
- Added a dependency-light supervised fraud baseline for labeled public datasets with ROC-AUC, average precision, precision at top 1%, lift, threshold tuning, and feature-weight reporting.
- Hardened the API with bounded query parameters, parameterized SQL, cache fallback behavior, `/health` and `/ready` endpoints, and CI-backed tests.
- Built a TypeScript dashboard showing live risk distribution, top risky users, recent suspicious bursts, and raw event history.

## Likely Interview Questions

### Is this a Kaggle project or a production project?

It is closer to a production systems project. Kaggle usually focuses on offline model performance on a fixed dataset. This project focuses on the real system around fraud detection: event ingestion, stream processing, storage design, APIs, caching, dashboards, and replay behavior.

### Did you use real datasets?

The repo can analyze and train on Kaggle-style CSVs such as PaySim, Credit Card Fraud Detection, and IEEE-CIS after downloading them locally. I do not commit those files because they are large and may require Kaggle account/license acceptance. I would not claim public synthetic or anonymized datasets prove production fraud performance, but they are useful for showing class imbalance, feature engineering, metric selection, and baseline model evaluation.

### Is the public demo actually running Kafka and Spark?

No. The public demo is a free static GitHub Pages build that simulates live events in the browser. The real Kafka, Spark, PostgreSQL, Redis, and FastAPI stack is runnable locally with Docker Compose. I separated those modes because free static hosting is reliable for recruiters, while the local stack demonstrates the actual system design.

### Why use rules instead of machine learning?

Rules are a practical online baseline when confirmed fraud labels are not available. They are explainable, quick to tune, and useful for analyst review. When labels exist, this repo now has a supervised baseline script that compares model scores using ROC-AUC, average precision, precision at top 1%, threshold precision/recall, false-positive rate, and lift.

### Is this production-level?

It is production-ready as a portfolio system, not production-certified for a bank. Production-grade fraud systems need private data, security review, authentication, monitoring, migrations, alert routing, model governance, compliance controls, and incident response. This project demonstrates the architecture and engineering habits: streaming ingestion, replay-safe storage, explainable scoring, operational APIs, caching, CI, a public demo, and a real-data evaluation path.

### Why Kafka?

Kafka decouples event producers from consumers, preserves ordered event streams by key, and lets downstream systems replay events. In this project, events are keyed by `user_id` to preserve per-user ordering within partitions.

### Why Spark Structured Streaming?

Spark gives a unified batch and streaming API, which is useful for feature engineering and recomputation. It also maps well to micro-batch aggregation, which is common for near-real-time risk scoring systems that do not need millisecond-level decisions.

### What happens if Kafka replays events?

Raw events are keyed by `event_id` in PostgreSQL. The stream writer inserts raw events with `ON CONFLICT DO NOTHING`, so duplicate event IDs are ignored. This gives practical idempotency even if the stream is replayed.

### Is the system exactly-once?

Not fully. The current design is replay-safe at the database boundary for raw events, but exactly-once across Kafka, Spark, and PostgreSQL is more nuanced. I would describe it as idempotent writes with deterministic recomputation, which is a realistic production pattern for this scale.

### What is the main bottleneck?

The streaming job currently recomputes user summaries from the full raw event history each micro-batch. That is simple and correct for a portfolio-sized dataset, but it would not scale indefinitely. The next version should use incremental aggregations, windowed state, or a feature store pattern.

### How would you reduce false positives?

I would measure alert volume and analyst outcomes, tune thresholds by segment, add allowlists or known-device history, and evaluate precision and recall once labels exist. I would also distinguish risk scoring from enforcement so high-risk events can trigger review instead of automatic blocking.

### How would you make it more production-ready?

I would add migrations, structured logging, metrics, tracing, dead-letter handling for malformed events, stronger schema validation, secrets management, load tests, retention policies, alert routing, model/rule versioning, time-based validation, calibration, and analyst feedback loops.

### What real-world impact does this have?

The system targets account takeover and suspicious financial activity. In a real product, a platform like this could help analysts identify high-risk users faster, preserve an audit trail, and reduce loss from unauthorized withdrawals or compromised accounts.

## Honest Limitations To Say Out Loud

- The bundled and hosted demo data is synthetic, so the demo itself does not prove fraud-model accuracy.
- Public downloaded datasets can train the baseline model, but they still do not replace private production labels.
- The stream job favors clarity over large-scale efficiency.
- There is no authentication or role-based access control yet.
- The database schema is created in code; production should use migrations.

Owning these limitations makes the project sound more mature, not less. It shows you know the difference between a strong portfolio system and a fully deployed fraud platform.
