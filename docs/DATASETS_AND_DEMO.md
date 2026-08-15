# Demo And Dataset Analysis

This repo now supports two demo paths:

1. A deterministic live demo using `data/demo_events.csv`.
2. Offline analysis of Kaggle-style fraud CSVs, with optional export into replayable dashboard events.
3. A free hosted GitHub Pages demo with simulated live events.
4. A dependency-light supervised baseline for labeled fraud CSVs.

## Free Hosted Demo

Expected public URL after the Pages workflow deploys:

```text
https://jasonavatarang.github.io/fraud-detection/
```

The hosted demo is intentionally static so it can stay free. It uses the same dashboard UI and risk-scoring concepts, but it simulates live events in the browser instead of running the Kafka, Spark, PostgreSQL, Redis, and FastAPI stack.

Deployment workflow:

```text
.github/workflows/pages.yml
```

The workflow builds the dashboard with:

```text
VITE_DEMO_MODE=true
VITE_BASE_PATH=/<repo-name>/
```

If GitHub Pages is not active yet, open the repo settings, go to Pages, and choose GitHub Actions as the publishing source.

## Live Dashboard Demo

Start the backend and dashboard:

```bash
docker compose up --build
npm run dev --prefix fraud-dashboard
```

Open:

```text
http://localhost:5173
```

Replay the scripted fraud scenario into Kafka:

```bash
docker compose --profile demo up demo-replay
```

Or run the replay script directly from your machine:

```bash
python -m pip install -r producer/requirements.txt
python producer/replay_events.py --file data/demo_events.csv --bootstrap-servers localhost:9092 --delay-seconds 0.5
```

To preview the exact events without Kafka:

```bash
python producer/replay_events.py --file data/demo_events.csv --dry-run --limit 5
```

## Dataset Options

Good datasets to try:

| Dataset | Best Use | Notes |
| --- | --- | --- |
| [PaySim Synthetic Financial Dataset](https://www.kaggle.com/datasets/ealaxi/paysim1) | Dashboard replay and event-style analysis | Has transaction types, account IDs, amounts, and `isFraud`. |
| [Credit Card Fraud Detection by ULB](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud) | Imbalance analysis and model baseline discussion | Highly imbalanced card transaction dataset with anonymized PCA features and `Class`. |
| [IEEE-CIS Fraud Detection](https://www.kaggle.com/competitions/ieee-fraud-detection) | Advanced feature engineering discussion | Rich transaction and identity data from a Kaggle competition. |

## Download With Kaggle CLI

Install and authenticate the Kaggle CLI first:

```bash
python -m pip install kaggle
```

Then place your Kaggle token at the default location used by the CLI. After that:

```bash
mkdir -p data/external/paysim
kaggle datasets download -d ealaxi/paysim1 -p data/external/paysim --unzip
```

```bash
mkdir -p data/external/creditcard
kaggle datasets download -d mlg-ulb/creditcardfraud -p data/external/creditcard --unzip
```

```bash
mkdir -p data/external/ieee
kaggle competitions download -c ieee-fraud-detection -p data/external/ieee
unzip data/external/ieee/ieee-fraud-detection.zip -d data/external/ieee
```

Downloaded data under `data/external/` is ignored by Git.

## Analyze A Dataset

Run the analyzer against any CSV:

```bash
python analysis/analyze_fraud_dataset.py \
  --csv data/external/paysim/PS_20174392719_1491204439457_log.csv \
  --report reports/paysim-analysis.md
```

The analyzer auto-detects common columns such as:

- `isFraud`, `Class`, `fraud`, `label`
- `amount`, `Amount`, `TransactionAmt`
- `type`, `ProductCD`, `transaction_type`
- `step`, `Time`, `TransactionDT`, `timestamp`
- `nameOrig`, `card1`, `customer_id`, `user_id`

## Train A Real-Data Baseline

After downloading a labeled fraud dataset, train a class-weighted logistic baseline:

```bash
python analysis/train_fraud_baseline.py \
  --csv data/external/paysim/PS_20174392719_1491204439457_log.csv \
  --output-dir models/paysim-baseline \
  --label-column isFraud \
  --max-rows 100000
```

For the Kaggle Credit Card Fraud dataset:

```bash
python analysis/train_fraud_baseline.py \
  --csv data/external/creditcard/creditcard.csv \
  --output-dir models/creditcard-baseline \
  --label-column Class \
  --max-rows 100000
```

For IEEE-CIS, begin with the transaction table:

```bash
python analysis/train_fraud_baseline.py \
  --csv data/external/ieee/train_transaction.csv \
  --output-dir models/ieee-transaction-baseline \
  --label-column isFraud \
  --max-rows 100000
```

The trainer writes:

- `metrics.json`: ROC-AUC, average precision, precision at top 1%, lift, threshold metrics, and confusion matrix.
- `model.json`: standard-library logistic regression weights and preprocessing metadata.
- `report.md`: interview-friendly markdown summary.

This is intentionally a baseline, not a winning Kaggle solution. It proves the project can move from raw labeled data to measurable fraud detection performance without depending on heavyweight notebook tooling.

## Export Dataset Rows Into Demo Events

You can project a dataset into this app's canonical event schema:

```bash
python analysis/analyze_fraud_dataset.py \
  --csv data/external/paysim/PS_20174392719_1491204439457_log.csv \
  --report reports/paysim-analysis.md \
  --export-events data/imported/paysim_events.csv \
  --export-limit 1000
```

Replay those projected events:

```bash
python producer/replay_events.py \
  --file data/imported/paysim_events.csv \
  --bootstrap-servers localhost:9092 \
  --delay-seconds 0.1
```

Important: the export is a dashboard demo projection. It converts labeled fraud rows into suspicious event sequences so the live system visibly responds. Use the generated analysis report for honest dataset findings; do not describe the projected stream as a trained fraud model.

## Interview Framing

If asked about Kaggle:

> I used Kaggle-style datasets for offline analysis and demo projection, but the main project is about the production system around fraud detection: ingestion, replay-safe storage, feature engineering, APIs, caching, CI, and dashboard operations.

If asked what would make the analysis stronger:

> I added a supervised baseline with train/test splits, class weighting, ROC-AUC, average precision, precision at alert-volume targets, lift, threshold selection, and feature weights. The next step would be stronger leakage checks, time-based validation, calibration, model monitoring, and analyst feedback labels.
