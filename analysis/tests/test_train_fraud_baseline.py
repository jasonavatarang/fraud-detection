import csv
import json

from analysis.train_fraud_baseline import (
    detect_label_column,
    infer_feature_spec,
    read_rows,
    train_baseline,
)


def write_training_fixture(path):
    rows = []
    for index in range(60):
        is_fraud = index % 10 in {0, 1}
        rows.append(
            {
                "TransactionID": f"T{index:04d}",
                "amount": "9500" if is_fraud else str(20 + index),
                "type": "CASH_OUT" if is_fraud else "PAYMENT",
                "failed_login_count": "3" if is_fraud else "0",
                "isFraud": "1" if is_fraud else "0",
            }
        )

    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def test_train_baseline_writes_metrics_model_and_report(tmp_path):
    dataset_path = tmp_path / "fraud_training.csv"
    output_dir = tmp_path / "model"
    write_training_fixture(dataset_path)

    metrics = train_baseline(
        csv_path=dataset_path,
        output_dir=output_dir,
        epochs=4,
        learning_rate=0.05,
        seed=7,
    )

    saved_metrics = json.loads((output_dir / "metrics.json").read_text())

    assert metrics["label_column"] == "isFraud"
    assert metrics["fraud_rows"] == 12
    assert metrics["roc_auc"] is not None
    assert metrics["average_precision"] is not None
    assert metrics["best_threshold"]["recall"] > 0
    assert saved_metrics["expanded_feature_count"] >= 3
    assert (output_dir / "model.json").exists()
    assert "# Fraud Model Benchmark" in (output_dir / "report.md").read_text()


def test_feature_inference_skips_identifier_like_columns(tmp_path):
    dataset_path = tmp_path / "fraud_training.csv"
    write_training_fixture(dataset_path)
    rows, columns = read_rows(dataset_path, max_rows=None)

    label_column = detect_label_column(columns, explicit_label=None)
    spec = infer_feature_spec(
        rows=rows,
        columns=columns,
        label_column=label_column,
        max_categories=8,
    )

    assert spec.skipped_columns["TransactionID"] == "identifier"
    assert "amount" in spec.numeric_columns
    assert "type" in spec.categorical_columns
