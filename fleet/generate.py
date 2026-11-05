"""Deterministic synthetic fleet data, including deliberate quality/replay fixtures."""

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fleet.config import Paths

START = datetime(2026, 10, 1, tzinfo=UTC)
REGIONS = ["Austin", "Dallas", "Denver"]


def timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def write_lines(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(r, sort_keys=True) if isinstance(r, dict) else r for r in rows)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(payload + "\n", encoding="utf-8")
    temporary.replace(path)


def generate(paths: Paths, vehicles: int = 24, days: int = 7, seed: int = 42) -> dict:
    if not 1 <= vehicles <= 500 or not 1 <= days <= 90:
        raise ValueError("Use 1–500 vehicles and 1–90 days.")
    # Never rewrite a landing directory already consumed by a file stream.
    if paths.landing.exists() and any(paths.landing.iterdir()):
        raise ValueError("Landing already contains data. Use a new --home for a fresh dataset.")
    rng = random.Random(seed)
    dimension, events = [], []
    for i in range(1, vehicles + 1):
        vehicle = f"EV-{i:03d}"
        region = REGIONS[(i - 1) % 3]
        base = {
            "vehicle_id": vehicle,
            "vehicle_sk": f"{vehicle}-v1",
            "model": ["Atlas Cargo", "Orion Shuttle", "Terra Utility"][i % 3],
            "region": region,
            "battery_capacity_kwh": [75.0, 90.0, 110.0][i % 3],
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2099-01-01T00:00:00Z",
        }
        if i == 4 and days >= 4:
            base["valid_to"] = timestamp(START + timedelta(days=3))
            dimension.append(base.copy())
            base.update(vehicle_sk=f"{vehicle}-v2", region="Denver", valid_from=base["valid_to"])
            base["valid_to"] = "2099-01-01T00:00:00Z"
        dimension.append(base)
        for day in range(days):
            date = START + timedelta(days=day)
            current_region = "Denver" if i == 4 and days >= 4 and day >= 3 else region
            center = {
                "Austin": (30.27, -97.74),
                "Dallas": (32.78, -96.80),
                "Denver": (39.74, -104.99),
            }[current_region]

            def event(kind, index, hour, vehicle=vehicle, day=day, date=date, **fields):
                return {
                    "event_id": f"{vehicle}-{day:02d}-{kind}-{index:02d}",
                    "vehicle_id": vehicle,
                    "event_type": kind,
                    "schema_version": 1,
                    "revision": 1,
                    "event_time": timestamp(date + timedelta(hours=hour)),
                    "emitted_at": timestamp(date + timedelta(hours=hour, minutes=2)),
                    **fields,
                }

            for hour in range(7, 19):
                hot = i % 8 == 0 and hour >= 16
                low = i % 7 == 0 and hour >= 17
                events.append(
                    event(
                        "telemetry",
                        hour,
                        hour,
                        latitude=round(center[0] + rng.uniform(-0.15, 0.15), 6),
                        longitude=round(center[1] + rng.uniform(-0.15, 0.15), 6),
                        speed_kph=round(rng.uniform(0, 115), 1),
                        soc_pct=round(rng.uniform(8, 14) if low else 88 - (hour - 7) * 5, 1),
                        battery_temp_c=round(
                            rng.uniform(46, 51) if hot else rng.uniform(25, 39), 1
                        ),
                    )
                )
            for trip in range(3):
                distance = round(rng.uniform(18, 85), 2)
                events.append(
                    event(
                        "trip",
                        trip,
                        8 + trip * 3,
                        distance_km=distance,
                        duration_min=round(distance * 1.3, 2),
                        energy_kwh=round(distance * rng.uniform(0.16, 0.27), 3),
                        route_id=f"R-{(i + trip) % 6 + 1:02d}",
                    )
                )
            kwh = round(rng.uniform(25, 55), 2)
            events.append(
                event(
                    "charging",
                    0,
                    21,
                    energy_kwh=kwh,
                    duration_min=round(kwh * 1.6, 2),
                    cost_usd=round(kwh * 0.18, 2),
                )
            )
            events.append(event("toll", 0, 12, cost_usd=round(rng.uniform(1, 8), 2)))
            if (i + day) % 5 == 0:
                events.append(
                    event(
                        "maintenance",
                        0,
                        20,
                        cost_usd=round(rng.uniform(45, 180), 2),
                        severity="warning" if i % 2 else "critical",
                        code="SYN-BAT-INSPECT",
                    )
                )
    # Three exact transport duplicates, one corrected event and deliberately invalid messages.
    duplicates = events[:3]
    corrected = next(e.copy() for e in events if e["event_type"] == "trip")
    corrected.update(revision=2, distance_km=corrected["distance_km"] + 5)
    invalid = [
        {**events[0], "event_id": "bad-soc", "soc_pct": 143},
        {**events[0], "event_id": "bad-vehicle", "vehicle_id": "EV-9999"},
        {**events[0], "event_id": "bad-version", "schema_version": 99},
        {**events[0], "event_id": "bad-time", "event_time": "yesterday"},
        "{malformed-json",
    ]
    rng.shuffle(events)
    # Last file contains an old event correction: event time is intentionally out of arrival order.
    rows = events + duplicates + invalid + [corrected]
    chunk = max(1, (len(rows) + 2) // 3)
    for index, offset in enumerate(range(0, len(rows), chunk)):
        write_lines(paths.landing / f"batch-{index:03d}.jsonl", rows[offset : offset + chunk])
    write_lines(paths.reference, dimension)
    manifest = {
        "seed": seed,
        "vehicles": vehicles,
        "days": days,
        "raw_lines": len(rows),
        "exact_duplicates": 3,
        "invalid_records": 5,
        "revision_updates": 1,
        "expected_silver_events": len(events),
        "synthetic": True,
    }
    (paths.root / "generator_manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
