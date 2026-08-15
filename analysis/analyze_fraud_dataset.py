import argparse
import csv
import hashlib
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


LABEL_CANDIDATES = ["isFraud", "is_fraud", "Class", "fraud", "fraud_flag", "label"]
AMOUNT_CANDIDATES = ["amount", "Amount", "TransactionAmt", "transaction_amount"]
TYPE_CANDIDATES = ["type", "event_type", "transaction_type", "ProductCD"]
TIME_CANDIDATES = ["timestamp", "event_time", "Time", "TransactionDT", "step"]
USER_CANDIDATES = ["user_id", "nameOrig", "account_id", "card1", "customer_id"]
DEVICE_CANDIDATES = ["device_id", "DeviceInfo", "card2", "nameDest"]
CANONICAL_COLUMNS = [
    "event_id",
    "user_id",
    "event_type",
    "timestamp",
    "ip_address",
    "location",
    "device_id",
    "amount",
    "status",
]


def normalize_name(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def find_column(columns: list[str], candidates: list[str]) -> str | None:
    normalized_columns = {normalize_name(column): column for column in columns}
    for candidate in candidates:
        match = normalized_columns.get(normalize_name(candidate))
        if match:
            return match
    return None


def parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def is_truthy_label(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "fraud"}


def summarize_numbers(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0}

    sorted_values = sorted(values)

    def percentile(percent: float) -> float:
        index = int(round((len(sorted_values) - 1) * percent))
        return sorted_values[index]

    return {
        "count": len(sorted_values),
        "min": sorted_values[0],
        "p25": percentile(0.25),
        "median": percentile(0.50),
        "p75": percentile(0.75),
        "p95": percentile(0.95),
        "max": sorted_values[-1],
        "mean": sum(sorted_values) / len(sorted_values),
    }


def detect_columns(columns: list[str]) -> dict[str, str | None]:
    return {
        "label": find_column(columns, LABEL_CANDIDATES),
        "amount": find_column(columns, AMOUNT_CANDIDATES),
        "type": find_column(columns, TYPE_CANDIDATES),
        "time": find_column(columns, TIME_CANDIDATES),
        "user": find_column(columns, USER_CANDIDATES),
        "device": find_column(columns, DEVICE_CANDIDATES),
    }


def profile_dataset(path: Path, max_rows: int | None = None, top_n: int = 10) -> dict[str, Any]:
    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        columns = reader.fieldnames or []
        detected = detect_columns(columns)

        row_count = 0
        fraud_count = 0
        label_counts: Counter[str] = Counter()
        missing_counts: Counter[str] = Counter()
        type_counts: Counter[str] = Counter()
        type_fraud_counts: Counter[str] = Counter()
        amount_values: list[float] = []
        fraud_amount_values: list[float] = []
        legitimate_amount_values: list[float] = []

        for row in reader:
            row_count += 1
            if max_rows is not None and row_count > max_rows:
                row_count -= 1
                break

            for column in columns:
                if row.get(column) in {None, ""}:
                    missing_counts[column] += 1

            is_fraud = False
            label_column = detected["label"]
            if label_column:
                label_value = row.get(label_column, "")
                label_counts[label_value] += 1
                is_fraud = is_truthy_label(label_value)
                if is_fraud:
                    fraud_count += 1

            amount_column = detected["amount"]
            amount = parse_float(row.get(amount_column)) if amount_column else None
            if amount is not None:
                amount_values.append(amount)
                if is_fraud:
                    fraud_amount_values.append(amount)
                else:
                    legitimate_amount_values.append(amount)

            type_column = detected["type"]
            if type_column:
                event_type = row.get(type_column, "unknown") or "unknown"
                type_counts[event_type] += 1
                if is_fraud:
                    type_fraud_counts[event_type] += 1

    type_fraud_rates = []
    for event_type, count in type_counts.most_common(top_n):
        frauds = type_fraud_counts[event_type]
        type_fraud_rates.append(
            {
                "value": event_type,
                "count": count,
                "fraud_count": frauds,
                "fraud_rate": frauds / count if count else 0,
            }
        )

    return {
        "path": str(path),
        "columns": columns,
        "detected": detected,
        "rows_scanned": row_count,
        "column_count": len(columns),
        "fraud_count": fraud_count,
        "fraud_rate": fraud_count / row_count if row_count else 0,
        "label_counts": label_counts.most_common(),
        "missing_counts": missing_counts.most_common(top_n),
        "amount_summary": summarize_numbers(amount_values),
        "fraud_amount_summary": summarize_numbers(fraud_amount_values),
        "legitimate_amount_summary": summarize_numbers(legitimate_amount_values),
        "type_fraud_rates": type_fraud_rates,
    }


def format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def format_number(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    return f"{value:,.2f}"


def render_amount_summary(title: str, summary: dict[str, float | int]) -> list[str]:
    if summary.get("count", 0) == 0:
        return [f"- {title}: no numeric amount values detected"]

    return [
        f"- {title}: count={summary['count']}, "
        f"mean={format_number(summary['mean'])}, "
        f"median={format_number(summary['median'])}, "
        f"p95={format_number(summary['p95'])}, "
        f"max={format_number(summary['max'])}"
    ]


def render_markdown_report(profile: dict[str, Any]) -> str:
    detected = profile["detected"]
    lines = [
        "# Fraud Dataset Analysis",
        "",
        f"Source: `{profile['path']}`",
        f"Rows scanned: {profile['rows_scanned']:,}",
        f"Columns: {profile['column_count']}",
        "",
        "## Detected Columns",
        "",
    ]
    for purpose, column in detected.items():
        lines.append(f"- {purpose}: `{column or 'not detected'}`")

    lines.extend(
        [
            "",
            "## Class Balance",
            "",
            f"- Fraud rows: {profile['fraud_count']:,}",
            f"- Fraud rate: {format_percent(profile['fraud_rate'])}",
        ]
    )

    if profile["label_counts"]:
        lines.append("- Label values:")
        for value, count in profile["label_counts"][:10]:
            lines.append(f"  - `{value}`: {count:,}")

    lines.extend(["", "## Amount Profile", ""])
    lines.extend(render_amount_summary("All rows", profile["amount_summary"]))
    lines.extend(render_amount_summary("Fraud rows", profile["fraud_amount_summary"]))
    lines.extend(
        render_amount_summary("Non-fraud rows", profile["legitimate_amount_summary"])
    )

    if profile["type_fraud_rates"]:
        lines.extend(["", "## Fraud Rate By Type", ""])
        lines.append("| Type | Rows | Fraud Rows | Fraud Rate |")
        lines.append("| --- | ---: | ---: | ---: |")
        for item in profile["type_fraud_rates"]:
            lines.append(
                f"| {item['value']} | {item['count']:,} | "
                f"{item['fraud_count']:,} | {format_percent(item['fraud_rate'])} |"
            )

    if profile["missing_counts"]:
        lines.extend(["", "## Most Missing Columns", ""])
        for column, count in profile["missing_counts"]:
            lines.append(f"- `{column}`: {count:,}")

    lines.extend(
        [
            "",
            "## Suggested Next Steps",
            "",
            "- Compare this label distribution against a naive all-legitimate baseline.",
            "- Add precision, recall, false-positive rate, and PR-AUC once model scores exist.",
            "- Use the export option only as a dashboard demo projection, not as proof of model accuracy.",
        ]
    )
    return "\n".join(lines) + "\n"


def stable_int(*parts: object, modulo: int = 10_000) -> int:
    joined = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % modulo


def stable_event_id(source: str, row_index: int, event_type: str, sequence: int) -> str:
    digest = hashlib.sha256(
        f"{source}|{row_index}|{event_type}|{sequence}".encode("utf-8")
    ).hexdigest()
    return f"import-{digest[:16]}"


def timestamp_for_row(row: dict[str, str], row_index: int, time_column: str | None) -> str:
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    if time_column:
        raw_value = row.get(time_column, "")
        numeric_value = parse_float(raw_value)
        if numeric_value is not None:
            multiplier = 3600 if normalize_name(time_column) == "step" else 1
            return (base_time + timedelta(seconds=numeric_value * multiplier)).isoformat()
        try:
            return datetime.fromisoformat(raw_value.replace("Z", "+00:00")).isoformat()
        except ValueError:
            pass
    return (base_time + timedelta(seconds=row_index * 5)).isoformat()


def map_transaction_type(raw_type: str | None, amount: float) -> str:
    value = (raw_type or "").strip().lower()
    if value in {"cash_out", "cashout", "transfer", "withdrawal"}:
        return "withdrawal"
    if value in {"payment", "debit", "cash_in", "cashin", "trade"}:
        return "trade"
    if amount >= 5000:
        return "withdrawal"
    return "trade"


def canonical_base_event(
    row: dict[str, str],
    row_index: int,
    detected: dict[str, str | None],
    source_name: str,
    event_type: str,
    sequence: int,
    amount: float,
    status: str = "success",
) -> dict[str, Any]:
    user_column = detected["user"]
    device_column = detected["device"]
    user_value = row.get(user_column, "") if user_column else ""
    device_value = row.get(device_column, "") if device_column else ""
    user_id = user_value or f"user_{stable_int(source_name, row_index, modulo=5000):04d}"
    device_id = device_value or f"device_{stable_int(user_id, modulo=1000):03d}"

    return {
        "event_id": stable_event_id(source_name, row_index, event_type, sequence),
        "user_id": user_id,
        "event_type": event_type,
        "timestamp": timestamp_for_row(row, row_index + sequence, detected["time"]),
        "ip_address": f"198.51.100.{stable_int(user_id, row_index, modulo=254) + 1}",
        "location": "dataset_import",
        "device_id": device_id,
        "amount": round(amount, 2),
        "status": status,
    }


def project_row_to_events(
    row: dict[str, str],
    row_index: int,
    detected: dict[str, str | None],
    source_name: str,
) -> list[dict[str, Any]]:
    amount_column = detected["amount"]
    type_column = detected["type"]
    label_column = detected["label"]
    amount = parse_float(row.get(amount_column)) if amount_column else None
    amount = amount or 0
    raw_type = row.get(type_column) if type_column else None
    mapped_type = map_transaction_type(raw_type, amount)
    is_fraud = is_truthy_label(row.get(label_column)) if label_column else False

    if not is_fraud:
        event_type = "login_success" if row_index % 5 == 0 else mapped_type
        return [
            canonical_base_event(
                row=row,
                row_index=row_index,
                detected=detected,
                source_name=source_name,
                event_type=event_type,
                sequence=0,
                amount=0 if event_type == "login_success" else amount,
            )
        ]

    return [
        canonical_base_event(
            row=row,
            row_index=row_index,
            detected=detected,
            source_name=source_name,
            event_type="login_failed",
            sequence=0,
            amount=0,
            status="failed",
        ),
        canonical_base_event(
            row=row,
            row_index=row_index,
            detected=detected,
            source_name=source_name,
            event_type="password_reset",
            sequence=1,
            amount=0,
        ),
        canonical_base_event(
            row=row,
            row_index=row_index,
            detected=detected,
            source_name=source_name,
            event_type="withdrawal",
            sequence=2,
            amount=max(amount, 5000),
        ),
    ]


def export_canonical_events(
    input_path: Path,
    output_path: Path,
    limit: int | None = None,
) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    exported = 0
    with input_path.open(newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        columns = reader.fieldnames or []
        detected = detect_columns(columns)

        with output_path.open("w", newline="", encoding="utf-8") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=CANONICAL_COLUMNS)
            writer.writeheader()

            for row_index, row in enumerate(reader, start=1):
                if limit is not None and row_index > limit:
                    break
                for event in project_row_to_events(row, row_index, detected, input_path.stem):
                    writer.writerow(event)
                    exported += 1
    return exported


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile a fraud dataset CSV and optionally export dashboard demo events."
    )
    parser.add_argument("--csv", type=Path, required=True, help="Input dataset CSV.")
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional row limit for profiling very large datasets.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional markdown report path.",
    )
    parser.add_argument(
        "--export-events",
        type=Path,
        default=None,
        help="Optional canonical CSV output for producer/replay_events.py.",
    )
    parser.add_argument(
        "--export-limit",
        type=int,
        default=1000,
        help="Maximum source rows to project when exporting events.",
    )
    parser.add_argument("--top-n", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile = profile_dataset(args.csv, max_rows=args.max_rows, top_n=args.top_n)
    report = render_markdown_report(profile)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")
        print(f"Wrote report to {args.report}")
    else:
        print(report)

    if args.export_events:
        exported = export_canonical_events(
            input_path=args.csv,
            output_path=args.export_events,
            limit=args.export_limit,
        )
        print(f"Exported {exported} canonical event(s) to {args.export_events}")


if __name__ == "__main__":
    main()
