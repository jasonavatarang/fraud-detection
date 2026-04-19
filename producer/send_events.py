import json
import random
import time
from datetime import datetime, timezone
from kafka import KafkaProducer
import uuid

producer = KafkaProducer(
    bootstrap_servers="kafka:9093",
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

locations = ["Miami", "New York", "Austin", "Chicago", "Boston", "Seattle", "Atlanta", "San Francisco"]
event_types = ["login_success", "login_failed", "password_reset", "trade", "withdrawal", "mfa_disabled", "profile_change"]
statuses = ["success", "failed"]

user_profiles = {
    "3001": {"home_location": "Miami", "device_ids": ["device_a", "device_b"]},
    "3002": {"home_location": "Austin", "device_ids": ["device_c"]},
    "3003": {"home_location": "Chicago", "device_ids": ["device_d", "device_e"]},
    "3004": {"home_location": "Boston", "device_ids": ["device_f"]},
    "3005": {"home_location": "Seattle", "device_ids": ["device_g", "device_h"]},
}


def random_ip():
    return f"203.0.113.{random.randint(1, 254)}"


def choose_event_type():
    weighted = (
        ["login_success"] * 35
        + ["login_failed"] * 20
        + ["trade"] * 15
        + ["withdrawal"] * 10
        + ["password_reset"] * 8
        + ["profile_change"] * 7
        + ["mfa_disabled"] * 5
    )
    return random.choice(weighted)


def generate_normal_event(user_id):
    profile = user_profiles[user_id]
    event_type = choose_event_type()

    if random.random() < 0.85:
        location = profile["home_location"]
    else:
        location = random.choice(locations)

    if random.random() < 0.85:
        device_id = random.choice(profile["device_ids"])
    else:
        device_id = f"device_{random.randint(100, 999)}"

    amount = 0.0
    if event_type == "trade":
        amount = round(random.uniform(50, 3000), 2)
    elif event_type == "withdrawal":
        amount = round(random.uniform(50, 6000), 2)

    status = "success"
    if event_type == "login_failed":
        status = "failed"

    return {
        "event_id": str(uuid.uuid4()),
        "user_id": user_id,
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip_address": random_ip(),
        "location": location,
        "device_id": device_id,
        "amount": amount,
        "status": status,
    }


def generate_fraud_burst(user_id):
    strange_location = random.choice([loc for loc in locations if loc != user_profiles[user_id]["home_location"]])
    strange_device = f"device_{random.randint(900, 999)}"
    ip = random_ip()
    now = datetime.now(timezone.utc).isoformat()

    events = [
        {
            "event_id": str(uuid.uuid4()),
            "user_id": user_id,
            "event_type": "login_failed",
            "timestamp": now,
            "ip_address": ip,
            "location": strange_location,
            "device_id": strange_device,
            "amount": 0.0,
            "status": "failed",
        },
        {
            "event_id": str(uuid.uuid4()),
            "user_id": user_id,
            "event_type": "login_failed",
            "timestamp": now,
            "ip_address": ip,
            "location": strange_location,
            "device_id": strange_device,
            "amount": 0.0,
            "status": "failed",
        },
        {
            "event_id": str(uuid.uuid4()),
            "user_id": user_id,
            "event_type": "password_reset",
            "timestamp": now,
            "ip_address": ip,
            "location": strange_location,
            "device_id": strange_device,
            "amount": 0.0,
            "status": "success",
        },
        {
            "event_id": str(uuid.uuid4()),
            "user_id": user_id,
            "event_type": "withdrawal",
            "timestamp": now,
            "ip_address": ip,
            "location": strange_location,
            "device_id": strange_device,
            "amount": round(random.uniform(5000, 15000), 2),
            "status": "success",
        },
    ]
    return events


def main():
    print("Starting random fraud traffic simulation...")

    while True:
        user_id = random.choice(list(user_profiles.keys()))

        if random.random() < 0.2:
            events = generate_fraud_burst(user_id)
            print(f"Sending fraud burst for user {user_id}")
            for event in events:
                # Keying by user_id helps preserve per user ordering in Kafka partitions.
                producer.send("fraud-events", key=user_id.encode("utf-8"), value=event)
                print("Sent:", event)
                time.sleep(1)
        else:
            event = generate_normal_event(user_id)
            producer.send("fraud-events", key=user_id.encode("utf-8"), value=event)
            print("Sent:", event)

        producer.flush()
        time.sleep(random.uniform(1, 3))


if __name__ == "__main__":
    main()