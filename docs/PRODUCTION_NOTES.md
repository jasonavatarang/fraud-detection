# Production Notes

## What Is Production-Style Already

- Kafka decouples event generation from stream processing.
- Raw events are immutable and keyed by `event_id`.
- Replayed events are ignored at the database boundary.
- Risk summaries are derived from the raw event source of truth.
- Redis improves dashboard/API latency without becoming the source of truth.
- API query limits are bounded and parameterized.
- `/health` and `/ready` expose service and dependency status.
- Public labeled fraud CSVs can be profiled and benchmarked with a supervised baseline.
- CI runs API tests and dashboard builds.

## What Is Not Production Yet

- The hosted demo uses simulated browser events so it can stay free.
- The repo does not include private production fraud data.
- There is no authentication, authorization, or analyst workflow management.
- The streaming job does not use schema registry, migrations, or dead-letter queues yet.
- The model benchmark uses a simple baseline and random split; regulated production systems need time-based validation, calibration, monitoring, and governance.

## Highest-Value Next Steps

1. Add database migrations with Alembic instead of creating tables inside the Spark job.
2. Add event schema validation and a dead-letter topic for malformed Kafka messages.
3. Replace full-history recomputation with incremental or windowed aggregations.
4. Add structured logs and metrics for event lag, batch duration, API latency, cache hit rate, and alert count.
5. Add authentication and role-based dashboard access.
6. Add rule versioning so alerts can be traced to the scoring logic that produced them.
7. Add labeled outcomes and evaluate precision, recall, and false-positive rate.
8. Promote the baseline model workflow into a versioned training pipeline with reproducible datasets, time-based splits, and model registry metadata.

## How This Could Become ML-Backed

The current rules and standard-library logistic benchmark are baselines. A realistic ML path would be:

1. Store analyst outcomes or confirmed chargeback/fraud labels.
2. Build offline features from the immutable raw event history.
3. Train and compare models against the rule baseline.
4. Select thresholds based on business cost, not accuracy alone.
5. Deploy model scores alongside rule scores.
6. Monitor drift, false positives, latency, and alert volume.

## Real-World Product Fit

This architecture fits products where risky user activity needs fast visibility:

- Fintech withdrawal monitoring.
- Account takeover detection.
- Marketplace seller or buyer risk monitoring.
- Crypto exchange account-security alerts.
- Internal security analytics for sensitive user actions.

The project is strongest when described as an operational fraud-risk platform with explainable scoring and a clear path toward supervised ML once labels exist.
