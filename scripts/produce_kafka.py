"""Publish synthetic JSONL to the optional local Kafka broker."""

import argparse
import hashlib
from pathlib import Path


def main():
    from kafka import KafkaProducer

    parser = argparse.ArgumentParser()
    parser.add_argument("--landing", type=Path, default=Path("data/landing"))
    parser.add_argument("--bootstrap-servers", default="localhost:9092")
    args = parser.parse_args()
    producer = KafkaProducer(bootstrap_servers=args.bootstrap_servers, acks="all", retries=3)
    sent = 0
    try:
        for file in sorted(args.landing.glob("*.jsonl")):
            for line in file.read_bytes().splitlines():
                producer.send("fleet.telemetry", key=hashlib.sha256(line).digest(), value=line).get(
                    timeout=20
                )
                sent += 1
        producer.flush(timeout=20)
    finally:
        producer.close(timeout=10)
    if not sent:
        raise SystemExit("No JSONL data found. Run fleet generate first.")
    print(f"Published {sent} synthetic messages to fleet.telemetry.")


if __name__ == "__main__":
    main()
