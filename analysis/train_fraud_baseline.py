import argparse
import csv
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from analysis.analyze_fraud_dataset import find_column, normalize_name, parse_float


LABEL_CANDIDATES = ["isFraud", "is_fraud", "Class", "fraud", "fraud_flag", "label"]
ID_LIKE_COLUMNS = {
    "eventid",
    "transactionid",
    "rowid",
    "index",
    "nameorig",
    "namedest",
    "userid",
    "customerid",
    "accountid",
    "deviceid",
}
MISSING_CATEGORY = "__MISSING__"
OTHER_CATEGORY = "__OTHER__"


@dataclass(frozen=True)
class FeatureSpec:
    numeric_columns: list[str]
    categorical_columns: dict[str, list[str]]
    skipped_columns: dict[str, str]


@dataclass(frozen=True)
class Preprocessor:
    feature_names: list[str]
    numeric_stats: dict[str, dict[str, float]]
    categorical_maps: dict[str, dict[str, int]]


def is_positive_label(value: str | None, positive_label: str = "1") -> int:
    if value is None:
        return 0
    normalized = value.strip().lower()
    if normalized == positive_label.strip().lower():
        return 1
    return int(normalized in {"true", "t", "yes", "y", "fraud"})


def read_rows(path: Path, max_rows: int | None) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        columns = reader.fieldnames or []
        rows: list[dict[str, str]] = []
        for row_index, row in enumerate(reader, start=1):
            if max_rows is not None and row_index > max_rows:
                break
            rows.append({column: row.get(column, "") for column in columns})
    return rows, columns


def detect_label_column(columns: list[str], explicit_label: str | None) -> str:
    if explicit_label:
        if explicit_label not in columns:
            raise ValueError(f"Label column `{explicit_label}` was not found in the CSV.")
        return explicit_label

    detected = find_column(columns, LABEL_CANDIDATES)
    if detected is None:
        raise ValueError(
            "Could not detect a fraud label column. Pass --label-column, for example "
            "`--label-column isFraud` or `--label-column Class`."
        )
    return detected


def should_skip_column(column: str, label_column: str) -> str | None:
    normalized = normalize_name(column)
    if column == label_column:
        return "label"
    if normalized in ID_LIKE_COLUMNS or normalized.endswith("id"):
        return "identifier"
    return None


def infer_feature_spec(
    rows: list[dict[str, str]],
    columns: list[str],
    label_column: str,
    max_categories: int,
) -> FeatureSpec:
    numeric_columns: list[str] = []
    categorical_columns: dict[str, list[str]] = {}
    skipped_columns: dict[str, str] = {}

    for column in columns:
        skip_reason = should_skip_column(column, label_column)
        if skip_reason:
            skipped_columns[column] = skip_reason
            continue

        non_missing = [row.get(column, "").strip() for row in rows if row.get(column, "").strip()]
        if not non_missing:
            skipped_columns[column] = "all_missing"
            continue

        numeric_count = sum(parse_float(value) is not None for value in non_missing)
        if numeric_count / len(non_missing) >= 0.95:
            numeric_columns.append(column)
            continue

        counts = Counter(non_missing)
        if 1 < len(counts) <= max_categories:
            categorical_columns[column] = [value for value, _ in counts.most_common()]
        else:
            skipped_columns[column] = f"high_cardinality_{len(counts)}"

    if not numeric_columns and not categorical_columns:
        raise ValueError("No usable numeric or low-cardinality categorical features were found.")

    return FeatureSpec(
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        skipped_columns=skipped_columns,
    )


def stratified_split(
    labels: list[int],
    test_size: float,
    seed: int,
) -> tuple[list[int], list[int]]:
    by_label: dict[int, list[int]] = defaultdict(list)
    for index, label in enumerate(labels):
        by_label[label].append(index)

    if len(by_label[1]) == 0 or len(by_label[0]) == 0:
        raise ValueError("Training requires at least one fraud row and one non-fraud row.")

    rng = random.Random(seed)
    train_indices: list[int] = []
    test_indices: list[int] = []
    for label, indices in by_label.items():
        rng.shuffle(indices)
        if len(indices) == 1:
            train_indices.extend(indices)
            continue
        test_count = max(1, int(round(len(indices) * test_size)))
        test_count = min(test_count, len(indices) - 1)
        test_indices.extend(indices[:test_count])
        train_indices.extend(indices[test_count:])

    rng.shuffle(train_indices)
    rng.shuffle(test_indices)
    return train_indices, test_indices


def mean_and_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 1.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    std = math.sqrt(variance)
    if std < 1e-12:
        std = 1.0
    return mean, std


def fit_preprocessor(
    rows: list[dict[str, str]],
    train_indices: list[int],
    feature_spec: FeatureSpec,
) -> Preprocessor:
    feature_names: list[str] = []
    numeric_stats: dict[str, dict[str, float]] = {}
    categorical_maps: dict[str, dict[str, int]] = {}

    for column in feature_spec.numeric_columns:
        values = [
            parsed
            for index in train_indices
            if (parsed := parse_float(rows[index].get(column))) is not None
        ]
        mean, std = mean_and_std(values)
        numeric_stats[column] = {"mean": mean, "std": std}
        feature_names.append(f"num:{column}")

    for column, configured_categories in feature_spec.categorical_columns.items():
        train_counts = Counter(
            (rows[index].get(column, "").strip() or MISSING_CATEGORY)
            for index in train_indices
        )
        categories = [
            category for category in configured_categories if category in train_counts
        ]
        if MISSING_CATEGORY in train_counts and MISSING_CATEGORY not in categories:
            categories.append(MISSING_CATEGORY)
        categories.append(OTHER_CATEGORY)

        mapping: dict[str, int] = {}
        for category in categories:
            mapping[category] = len(feature_names)
            feature_names.append(f"cat:{column}={category}")
        categorical_maps[column] = mapping

    return Preprocessor(
        feature_names=feature_names,
        numeric_stats=numeric_stats,
        categorical_maps=categorical_maps,
    )


def row_to_features(row: dict[str, str], preprocessor: Preprocessor) -> dict[int, float]:
    features: dict[int, float] = {}

    for feature_index, (column, stats) in enumerate(preprocessor.numeric_stats.items()):
        value = parse_float(row.get(column))
        if value is None:
            value = stats["mean"]
        features[feature_index] = (value - stats["mean"]) / stats["std"]

    for column, mapping in preprocessor.categorical_maps.items():
        value = row.get(column, "").strip() or MISSING_CATEGORY
        feature_index = mapping.get(value, mapping[OTHER_CATEGORY])
        features[feature_index] = 1.0

    return features


def sigmoid(value: float) -> float:
    if value >= 35:
        return 1.0
    if value <= -35:
        return 0.0
    return 1.0 / (1.0 + math.exp(-value))


def score(features: dict[int, float], weights: list[float], bias: float) -> float:
    return bias + sum(weights[index] * value for index, value in features.items())


def train_logistic_regression(
    feature_rows: list[dict[int, float]],
    labels: list[int],
    train_indices: list[int],
    epochs: int,
    learning_rate: float,
    l2: float,
    seed: int,
    max_class_weight: float,
) -> tuple[list[float], float]:
    feature_count = 0
    for features in feature_rows:
        if features:
            feature_count = max(feature_count, max(features) + 1)

    weights = [0.0] * feature_count
    bias = 0.0
    positive_count = sum(labels[index] for index in train_indices)
    negative_count = len(train_indices) - positive_count
    positive_weight = min(max_class_weight, negative_count / max(positive_count, 1))
    rng = random.Random(seed)

    ordered_indices = list(train_indices)
    for epoch in range(epochs):
        rng.shuffle(ordered_indices)
        step = learning_rate / math.sqrt(epoch + 1)
        for row_index in ordered_indices:
            features = feature_rows[row_index]
            label = labels[row_index]
            prediction = sigmoid(score(features, weights, bias))
            sample_weight = positive_weight if label == 1 else 1.0
            error = (prediction - label) * sample_weight

            bias -= step * error
            for feature_index, value in features.items():
                gradient = error * value + l2 * weights[feature_index]
                weights[feature_index] -= step * gradient

    return weights, bias


def predict_probabilities(
    feature_rows: list[dict[int, float]],
    indices: list[int],
    weights: list[float],
    bias: float,
) -> list[float]:
    return [sigmoid(score(feature_rows[index], weights, bias)) for index in indices]


def roc_auc(labels: list[int], probabilities: list[float]) -> float | None:
    positive_count = sum(labels)
    negative_count = len(labels) - positive_count
    if positive_count == 0 or negative_count == 0:
        return None

    pairs = sorted(zip(probabilities, labels), key=lambda item: item[0])
    rank_sum = 0.0
    index = 0
    while index < len(pairs):
        tie_end = index
        while tie_end < len(pairs) and pairs[tie_end][0] == pairs[index][0]:
            tie_end += 1
        average_rank = (index + 1 + tie_end) / 2
        positives_in_tie = sum(label for _, label in pairs[index:tie_end])
        rank_sum += positives_in_tie * average_rank
        index = tie_end

    return (rank_sum - positive_count * (positive_count + 1) / 2) / (
        positive_count * negative_count
    )


def average_precision(labels: list[int], probabilities: list[float]) -> float | None:
    positive_count = sum(labels)
    if positive_count == 0:
        return None

    pairs = sorted(zip(probabilities, labels), key=lambda item: item[0], reverse=True)
    true_positives = 0
    precision_sum = 0.0
    for rank, (_, label) in enumerate(pairs, start=1):
        if label == 1:
            true_positives += 1
            precision_sum += true_positives / rank
    return precision_sum / positive_count


def confusion_at_threshold(
    labels: list[int],
    probabilities: list[float],
    threshold: float,
) -> dict[str, float | int]:
    true_positive = false_positive = true_negative = false_negative = 0
    for label, probability in zip(labels, probabilities):
        predicted = int(probability >= threshold)
        if predicted == 1 and label == 1:
            true_positive += 1
        elif predicted == 1 and label == 0:
            false_positive += 1
        elif predicted == 0 and label == 0:
            true_negative += 1
        else:
            false_negative += 1

    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    false_positive_rate = false_positive / max(false_positive + true_negative, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    return {
        "threshold": threshold,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "true_negative": true_negative,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "false_positive_rate": false_positive_rate,
        "f1": f1,
    }


def best_f1_threshold(labels: list[int], probabilities: list[float]) -> dict[str, float | int]:
    pairs = sorted(zip(probabilities, labels), key=lambda item: item[0], reverse=True)
    total_positive = sum(labels)
    true_positive = false_positive = 0
    best = confusion_at_threshold(labels, probabilities, 0.5)
    index = 0

    while index < len(pairs):
        threshold = pairs[index][0]
        while index < len(pairs) and pairs[index][0] == threshold:
            if pairs[index][1] == 1:
                true_positive += 1
            else:
                false_positive += 1
            index += 1

        false_negative = total_positive - true_positive
        true_negative = len(labels) - total_positive - false_positive
        precision = true_positive / max(true_positive + false_positive, 1)
        recall = true_positive / max(true_positive + false_negative, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-12)
        candidate = {
            "threshold": threshold,
            "true_positive": true_positive,
            "false_positive": false_positive,
            "true_negative": true_negative,
            "false_negative": false_negative,
            "precision": precision,
            "recall": recall,
            "false_positive_rate": false_positive
            / max(false_positive + true_negative, 1),
            "f1": f1,
        }
        if candidate["f1"] > best["f1"]:
            best = candidate

    return best


def precision_at_fraction(
    labels: list[int],
    probabilities: list[float],
    fraction: float,
) -> float | None:
    if not labels:
        return None
    k = max(1, int(round(len(labels) * fraction)))
    pairs = sorted(zip(probabilities, labels), key=lambda item: item[0], reverse=True)
    selected = pairs[:k]
    return sum(label for _, label in selected) / len(selected)


def top_weighted_features(
    feature_names: list[str],
    weights: list[float],
    limit: int = 10,
) -> dict[str, list[dict[str, float | str]]]:
    pairs = list(zip(feature_names, weights))
    positive = sorted(pairs, key=lambda item: item[1], reverse=True)[:limit]
    negative = sorted(pairs, key=lambda item: item[1])[:limit]
    return {
        "positive": [{"feature": feature, "weight": weight} for feature, weight in positive],
        "negative": [{"feature": feature, "weight": weight} for feature, weight in negative],
    }


def format_metric(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return str(value)
    return f"{value:.4f}"


def render_report(metrics: dict[str, Any]) -> str:
    lines = [
        "# Fraud Model Benchmark",
        "",
        f"Source: `{metrics['source_csv']}`",
        f"Label column: `{metrics['label_column']}`",
        f"Rows loaded: {metrics['rows_loaded']:,}",
        f"Train rows: {metrics['train_rows']:,}",
        f"Test rows: {metrics['test_rows']:,}",
        f"Fraud rate: {metrics['fraud_rate'] * 100:.4f}%",
        "",
        "## Feature Summary",
        "",
        f"- Numeric features: {metrics['numeric_feature_count']}",
        f"- Categorical feature groups: {metrics['categorical_feature_group_count']}",
        f"- Expanded model features: {metrics['expanded_feature_count']}",
        f"- Skipped columns: {metrics['skipped_column_count']}",
        "",
        "## Test Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| ROC-AUC | {format_metric(metrics['roc_auc'])} |",
        f"| Average precision | {format_metric(metrics['average_precision'])} |",
        f"| Precision at top 1% | {format_metric(metrics['precision_at_1_percent'])} |",
        f"| Lift at top 1% | {format_metric(metrics['lift_at_1_percent'])} |",
        f"| Best F1 threshold | {format_metric(metrics['best_threshold']['threshold'])} |",
        f"| Best F1 | {format_metric(metrics['best_threshold']['f1'])} |",
        f"| Best-threshold precision | {format_metric(metrics['best_threshold']['precision'])} |",
        f"| Best-threshold recall | {format_metric(metrics['best_threshold']['recall'])} |",
        f"| Best-threshold false-positive rate | {format_metric(metrics['best_threshold']['false_positive_rate'])} |",
        "",
        "## Confusion Matrix At Best Threshold",
        "",
        "| Actual / Predicted | Legitimate | Fraud |",
        "| --- | ---: | ---: |",
        (
            f"| Legitimate | {metrics['best_threshold']['true_negative']} | "
            f"{metrics['best_threshold']['false_positive']} |"
        ),
        (
            f"| Fraud | {metrics['best_threshold']['false_negative']} | "
            f"{metrics['best_threshold']['true_positive']} |"
        ),
        "",
        "## Top Positive Risk Features",
        "",
    ]
    for item in metrics["top_features"]["positive"]:
        lines.append(f"- `{item['feature']}`: {item['weight']:.4f}")

    lines.extend(["", "## Top Negative Risk Features", ""])
    for item in metrics["top_features"]["negative"]:
        lines.append(f"- `{item['feature']}`: {item['weight']:.4f}")

    lines.extend(
        [
            "",
            "## How To Discuss This",
            "",
            "- Treat these results as a reproducible baseline, not final fraud performance.",
            "- For real production use, validate on time-based splits and analyst-confirmed labels.",
            "- Optimize for recall, precision, false-positive rate, and review capacity, not accuracy.",
        ]
    )
    return "\n".join(lines) + "\n"


def train_baseline(
    csv_path: Path,
    output_dir: Path,
    label_column: str | None = None,
    positive_label: str = "1",
    max_rows: int | None = 100_000,
    test_size: float = 0.2,
    seed: int = 42,
    max_categories: int = 32,
    epochs: int = 8,
    learning_rate: float = 0.03,
    l2: float = 0.0001,
    max_class_weight: float = 50.0,
) -> dict[str, Any]:
    rows, columns = read_rows(csv_path, max_rows=max_rows)
    if len(rows) < 10:
        raise ValueError("At least 10 rows are required for a meaningful train/test split.")

    resolved_label_column = detect_label_column(columns, label_column)
    labels = [
        is_positive_label(row.get(resolved_label_column), positive_label=positive_label)
        for row in rows
    ]
    train_indices, test_indices = stratified_split(labels, test_size=test_size, seed=seed)
    feature_spec = infer_feature_spec(
        rows=rows,
        columns=columns,
        label_column=resolved_label_column,
        max_categories=max_categories,
    )
    preprocessor = fit_preprocessor(rows, train_indices, feature_spec)
    feature_rows = [row_to_features(row, preprocessor) for row in rows]

    weights, bias = train_logistic_regression(
        feature_rows=feature_rows,
        labels=labels,
        train_indices=train_indices,
        epochs=epochs,
        learning_rate=learning_rate,
        l2=l2,
        seed=seed,
        max_class_weight=max_class_weight,
    )

    test_labels = [labels[index] for index in test_indices]
    probabilities = predict_probabilities(feature_rows, test_indices, weights, bias)
    fraud_rate = sum(labels) / len(labels)
    precision_top_1 = precision_at_fraction(test_labels, probabilities, 0.01)
    metrics = {
        "source_csv": str(csv_path),
        "label_column": resolved_label_column,
        "rows_loaded": len(rows),
        "train_rows": len(train_indices),
        "test_rows": len(test_indices),
        "fraud_rows": sum(labels),
        "fraud_rate": fraud_rate,
        "numeric_feature_count": len(feature_spec.numeric_columns),
        "categorical_feature_group_count": len(feature_spec.categorical_columns),
        "expanded_feature_count": len(preprocessor.feature_names),
        "skipped_column_count": len(feature_spec.skipped_columns),
        "roc_auc": roc_auc(test_labels, probabilities),
        "average_precision": average_precision(test_labels, probabilities),
        "precision_at_1_percent": precision_top_1,
        "lift_at_1_percent": precision_top_1 / fraud_rate if precision_top_1 is not None and fraud_rate else None,
        "threshold_0_5": confusion_at_threshold(test_labels, probabilities, 0.5),
        "best_threshold": best_f1_threshold(test_labels, probabilities),
        "top_features": top_weighted_features(preprocessor.feature_names, weights),
        "configuration": {
            "max_rows": max_rows,
            "test_size": test_size,
            "seed": seed,
            "max_categories": max_categories,
            "epochs": epochs,
            "learning_rate": learning_rate,
            "l2": l2,
            "max_class_weight": max_class_weight,
        },
    }

    model = {
        "model_type": "standard_library_weighted_logistic_regression",
        "label_column": resolved_label_column,
        "positive_label": positive_label,
        "bias": bias,
        "weights": weights,
        "feature_names": preprocessor.feature_names,
        "numeric_stats": preprocessor.numeric_stats,
        "categorical_maps": preprocessor.categorical_maps,
        "best_threshold": metrics["best_threshold"]["threshold"],
        "skipped_columns": feature_spec.skipped_columns,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "model.json").write_text(
        json.dumps(model, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(render_report(metrics), encoding="utf-8")
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train a dependency-light fraud baseline on a labeled Kaggle-style CSV "
            "and write metrics/model artifacts."
        )
    )
    parser.add_argument("--csv", type=Path, required=True, help="Input labeled fraud CSV.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("models/fraud_baseline"),
        help="Directory for metrics.json, model.json, and report.md.",
    )
    parser.add_argument("--label-column", default=None)
    parser.add_argument("--positive-label", default="1")
    parser.add_argument("--max-rows", type=int, default=100_000)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-categories", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument("--l2", type=float, default=0.0001)
    parser.add_argument("--max-class-weight", type=float, default=50.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metrics = train_baseline(
        csv_path=args.csv,
        output_dir=args.output_dir,
        label_column=args.label_column,
        positive_label=args.positive_label,
        max_rows=args.max_rows,
        test_size=args.test_size,
        seed=args.seed,
        max_categories=args.max_categories,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        l2=args.l2,
        max_class_weight=args.max_class_weight,
    )
    print(render_report(metrics))
    print(f"Wrote model artifacts to {args.output_dir}")


if __name__ == "__main__":
    main()
