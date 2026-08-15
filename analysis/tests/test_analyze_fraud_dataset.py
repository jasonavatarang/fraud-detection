import csv

from analysis.analyze_fraud_dataset import (
    export_canonical_events,
    profile_dataset,
)


def write_sample_dataset(path):
    rows = [
        {
            "step": "1",
            "type": "PAYMENT",
            "amount": "42.50",
            "nameOrig": "C1001",
            "nameDest": "M9001",
            "isFraud": "0",
        },
        {
            "step": "2",
            "type": "CASH_OUT",
            "amount": "7500",
            "nameOrig": "C2002",
            "nameDest": "C9002",
            "isFraud": "1",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def test_profile_dataset_detects_common_fraud_columns(tmp_path):
    dataset_path = tmp_path / "paysim_sample.csv"
    write_sample_dataset(dataset_path)

    profile = profile_dataset(dataset_path)

    assert profile["rows_scanned"] == 2
    assert profile["detected"]["label"] == "isFraud"
    assert profile["detected"]["amount"] == "amount"
    assert profile["detected"]["type"] == "type"
    assert profile["fraud_count"] == 1
    assert profile["fraud_rate"] == 0.5


def test_export_canonical_events_projects_fraud_rows_into_demo_burst(tmp_path):
    dataset_path = tmp_path / "paysim_sample.csv"
    events_path = tmp_path / "events.csv"
    write_sample_dataset(dataset_path)

    exported = export_canonical_events(dataset_path, events_path)

    with events_path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert exported == 4
    assert rows[0]["event_type"] == "trade"
    assert [row["event_type"] for row in rows[1:]] == [
        "login_failed",
        "password_reset",
        "withdrawal",
    ]
    assert rows[-1]["user_id"] == "C2002"
    assert float(rows[-1]["amount"]) == 7500
