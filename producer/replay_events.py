import argparse
import csv
import json
import os
import time
from pathlib import Path
from typing import Any, Iterable


REQUIRED_COLUMNS = [
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


def normalize_event(row: dict[str, str], row_number: int) -> dict[str, Any]:
    missing = [column for column in REQUIRED_COLUMNS if column not in row]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Row {row_number} is missing required columns: {joined}")

    event = {column: row[column] for column in REQUIRED_COLUMNS}
    event["amount"] = float(event["amount"] or 0)
    return event


def read_events(path: Path, limit: int | None = None) -> Iterable[dict[str, Any]]:
    with path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for index, row in enumerate(reader, start=1):
            if limit is not None and index > limit:
                break
            yield normalize_event(row, index)


def send_events(
    events: Iterable[dict[str, Any]],
    bootstrap_servers: str,
    topic: str,
    delay_seconds: float,
    dry_run: bool,
) -> int:
    producer = None
    if not dry_run:
        from kafka import KafkaProducer

        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        )

    sent = 0
    for event in events:
        sent += 1
        if dry_run:
            print(json.dumps(event, sort_keys=True))
        else:
            assert producer is not None
            producer.send(topic, key=event["user_id"].encode("utf-8"), value=event)
            producer.flush()
            print(f"Sent {event['event_id']} for user {event['user_id']}")

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    if producer is not None:
        producer.close()

    return sent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay canonical fraud events into Kafka for demos."
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("data/demo_events.csv"),
        help="CSV file with canonical fraud event columns.",
    )
    parser.add_argument(
        "--bootstrap-servers",
        default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        help="Kafka bootstrap servers.",
    )
    parser.add_argument(
        "--topic",
        default=os.getenv("KAFKA_TOPIC", "fraud-events"),
        help="Kafka topic to publish to.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.2,
        help="Delay between events so the dashboard visibly changes.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print events without connecting to Kafka.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    events = read_events(args.file, limit=args.limit)
    sent = send_events(
        events=events,
        bootstrap_servers=args.bootstrap_servers,
        topic=args.topic,
        delay_seconds=args.delay_seconds,
        dry_run=args.dry_run,
    )
    action = "Prepared" if args.dry_run else "Sent"
    print(f"{action} {sent} event(s) from {args.file}")


if __name__ == "__main__":
    main()
