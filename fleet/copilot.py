"""Llama chooses a bounded read tool; only verified data produces the answer."""

import json
import os
import re
import threading
import time
from collections import deque
from decimal import Decimal
from pathlib import Path
from typing import Literal

import duckdb
import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=3, max_length=1000)

    @field_validator("message")
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if len(value) < 3 or any(ord(c) < 32 and c not in "\n\t" for c in value):
            raise ValueError("Enter a fleet question between 3 and 1000 characters.")
        return value


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: Literal["overview", "ranking", "compare", "trips", "quality", "unsupported"]
    region: Literal["All", "Austin", "Dallas", "Denver"] = "All"
    vehicle_id: str | None = Field(default=None, pattern=r"^EV-\d{3,4}$")
    metric: Literal["energy", "efficiency", "alerts", "cost", "distance"] = "energy"


class ChatResponse(BaseModel):
    answer: str
    mode: Literal["llama", "fallback", "guardrail"]
    notice: str
    intent: Intent
    data: list[dict] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    run_id: str | None = None
    period: str | None = None
    request_id: str
    synthetic: bool = True


class RateLimiter:
    """Process-wide local-demo budget, deliberately not trusting forwarded IP headers."""

    def __init__(self, limit=20):
        self.limit = limit
        self.events = deque()
        self.lock = threading.Lock()

    def check(self):
        with self.lock:
            now = time.monotonic()
            while self.events and self.events[0] <= now - 60:
                self.events.popleft()
            if len(self.events) >= self.limit:
                raise HTTPException(
                    429,
                    "Chat is busy. Please try again in a minute.",
                    headers={"Retry-After": "60"},
                )
            self.events.append(now)


def fallback_intent(message: str) -> Intent:
    text = message.lower()
    regions = [r for r in ("Austin", "Dallas", "Denver") if r.lower() in text]
    vehicle = re.search(r"\bev-\d{3,4}\b", text)
    metric = "energy"
    for words, name in [
        ("efficien", "efficiency"),
        ("alert", "alerts"),
        ("cost", "cost"),
        ("distance", "distance"),
    ]:
        if words in text:
            metric = name
    if any(w in text for w in ("quarantin", "validation", "quality", "invalid", "failed record")):
        tool = "quality"
    elif "compare" in text or len(regions) > 1:
        tool = "compare"
    elif "trip" in text and vehicle:
        tool = "trips"
    elif any(w in text for w in ("highest", "most", "top", "rank")):
        tool = "ranking"
    elif any(w in text for w in ("fleet", "vehicle", "overview", "summary", "energy", "cost")):
        tool = "overview"
    else:
        tool = "unsupported"
    return Intent(
        tool=tool,
        region=regions[0] if len(regions) == 1 else "All",
        vehicle_id=vehicle.group().upper() if vehicle else None,
        metric=metric,
    )


def guardrail(message: str) -> str | None:
    text = message.lower()
    if re.search(r"\b(delete|drop|update|insert|execute|password|secret|ignore|override)\b", text):
        return "I can only read published fleet analytics. I cannot change data or reveal secrets."
    if re.search(r"\b(maintenance|repair|diagnos\w*|replace|predict\w*|forecast\w*)\b", text):
        return (
            "I cannot diagnose vehicles or predict maintenance from these aggregates. "
            "Ask which vehicles have the most recorded alerts instead; alerts are not diagnoses."
        )
    if re.search(
        r"\b(today|yesterday|tomorrow|last|this|since|before|after|between)\b|\d{4}-\d{2}", text
    ):
        return (
            "This version answers over the full published reporting period only. "
            "Please ask without a date filter; every result shows its actual date range."
        )
    if re.search(r"\b(lowest|least|cheapest|best|bottom)\b", text):
        return (
            "Rankings currently show the top 5 by descending value. "
            "Ask for highest energy, alerts, cost, or distance."
        )
    if len(re.findall(r"\bev-\d{3,4}\b", text)) > 1:
        return "Please ask about one vehicle at a time, or compare fleet regions."
    return None


def classify(message: str, client: httpx.Client | None = None) -> tuple[Intent, str]:
    """No cloud endpoint and no unvalidated model text reaches the user or SQL engine."""
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    # Fixed operator configuration, never taken from an HTTP request.
    model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    prompt = (
        "Classify a fleet analytics question as JSON matching the schema. Never output SQL. "
        "Tools: overview=totals or single vehicle summary, ranking=top 5 vehicles descending "
        "by metric, compare=all region summaries, trips=recent trips for an explicit vehicle, "
        "quality=pipeline validation counts. Unsupported questions must use unsupported. "
        "Only Austin, Dallas, Denver are supported regions. Do not invent vehicle IDs. "
        "Use All unless an explicit supported region is named. Default metric is energy. "
        "No date filters, predictions, write actions, or conversation history are supported."
    )
    payload = {
        "model": model,
        "stream": False,
        "format": Intent.model_json_schema(),
        "options": {"temperature": 0, "num_predict": 180},
        "keep_alive": "5m",
        "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": message}],
    }
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(25, connect=2), trust_env=False)
    try:
        for attempt in range(2):
            try:
                response = client.post(base + "/api/chat", json=payload)
                response.raise_for_status()
                content = response.json()["message"]["content"]
                if len(content) > 6000:
                    raise ValueError("Oversized classification")
                intent = Intent.model_validate_json(content)
                # The model may choose a tool, but cannot invent or remove an explicit ID/region.
                explicit = fallback_intent(message)
                intent.vehicle_id = explicit.vehicle_id
                intent.region = explicit.region
                return intent, "llama"
            except (httpx.ConnectError, httpx.ReadError):
                if attempt == 0:
                    time.sleep(0.2)
                    continue
                break
            except (httpx.HTTPError, ValueError, KeyError, TypeError, ValidationError):
                break
    finally:
        if owned:
            client.close()
    return fallback_intent(message), "fallback"


METRICS = {
    "energy": "sum(consumed_kwh)",
    "efficiency": "100 * sum(consumed_kwh) / nullif(sum(distance_km), 0)",
    "alerts": "sum(alert_count)",
    "cost": "sum(operating_cost_usd)",
    "distance": "sum(distance_km)",
}
UNITS = {
    "energy": "kWh",
    "efficiency": "kWh/100 km (higher means less efficient)",
    "alerts": "recorded alerts",
    "cost": "USD",
    "distance": "km",
}


def query(conn, sql, params=()):
    result = conn.execute(sql, params)
    return [
        dict(
            zip(
                [c[0] for c in result.description],
                [float(v) if isinstance(v, Decimal) else v for v in row],
                strict=True,
            )
        )
        for row in result.fetchall()
    ]


def answer(current: Path, intent: Intent) -> dict:
    """One immutable serving snapshot per answer. All identifiers are application-owned."""
    with duckdb.connect(str(current / "analytics.duckdb"), read_only=True) as conn:
        dates = conn.execute("SELECT min(event_date), max(event_date) FROM mart_fleet").fetchone()
        period = f"{dates[0]} to {dates[1]}"
        clause = "(? = 'All' OR region = ?) AND (? IS NULL OR vehicle_id = ?)"
        params = [intent.region, intent.region, intent.vehicle_id, intent.vehicle_id]
        source = "mart_fleet"
        if intent.tool == "quality":
            report = json.loads((current / "report.json").read_text())
            data = [
                {
                    k: report.get(k)
                    for k in (
                        "bronze_unique_payloads",
                        "quarantined",
                        "silver_events",
                        "quality_pass_pct",
                        "superseded_revisions",
                    )
                }
            ]
            source = "report.json"
            text = (
                "Published pipeline quality counts (all regions and vehicles). "
                "Missing values mean not recorded."
            )
        elif intent.tool == "trips":
            if intent.vehicle_id is None:
                return {
                    "answer": "Which vehicle? Please include an ID such as EV-008.",
                    "data": [],
                    "sources": [],
                    "period": period,
                    "run_id": current.name,
                }
            source = "fact_trip"
            data = query(
                conn,
                """SELECT event_id, date_key, region, distance_km, energy_kwh
                FROM fact_trip WHERE vehicle_id = ? AND (? = 'All' OR region = ?)
                ORDER BY event_ts DESC, event_id LIMIT 10""",
                [intent.vehicle_id, intent.region, intent.region],
            )
            text = (
                f"Up to 10 most recent recorded trips for {intent.vehicle_id}; "
                f"region: {intent.region}."
            )
        elif intent.tool == "ranking":
            data = query(
                conn,
                f"""SELECT vehicle_id, round({METRICS[intent.metric]}, 3) AS value
                FROM mart_fleet WHERE {clause} GROUP BY vehicle_id
                ORDER BY value DESC NULLS LAST, vehicle_id LIMIT 5""",
                params,
            )
            text = (
                f"Top 5 vehicles by {intent.metric}, descending; "
                f"units: {UNITS[intent.metric]}. Region: {intent.region}."
            )
        elif intent.tool == "compare":
            data = query(
                conn,
                """SELECT region, count(DISTINCT vehicle_id) AS vehicles,
                round(sum(distance_km), 2) AS distance_km,
                round(100 * sum(consumed_kwh) / nullif(sum(distance_km), 0), 3) AS kwh_per_100km,
                round(sum(operating_cost_usd), 2) AS cost_usd, sum(alert_count) AS alerts
                FROM mart_fleet WHERE (? IS NULL OR vehicle_id = ?)
                GROUP BY region ORDER BY region""",
                [intent.vehicle_id, intent.vehicle_id],
            )
            text = (
                "Comparison of all published regions. Efficiency is distance-weighted; "
                "lower kWh/100 km is better."
            )
        else:
            data = query(
                conn,
                f"""SELECT count(DISTINCT vehicle_id) AS vehicles,
                sum(trip_count) AS trips, round(sum(distance_km), 2) AS distance_km,
                round(sum(consumed_kwh), 3) AS energy_kwh,
                round(sum(operating_cost_usd), 2) AS cost_usd,
                sum(alert_count) AS alerts FROM mart_fleet WHERE {clause}""",
                params,
            )
            text = (
                f"Fleet summary — region: {intent.region}; vehicle: {intent.vehicle_id or 'All'}."
            )
            if data[0]["vehicles"] == 0:
                data = []
        if not data:
            text = (
                "No matching records exist in this published snapshot. "
                "Check the vehicle ID and region."
            )
        return {
            "answer": text,
            "data": data,
            "sources": [source],
            "period": period,
            "run_id": current.name,
        }
