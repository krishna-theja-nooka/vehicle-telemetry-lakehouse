import json

import duckdb
import pytest
from fastapi.testclient import TestClient

from fleet.api import create_app


@pytest.fixture
def client(paths):
    run_id = "20261001T000000-abcdef12"
    current = paths.serving / run_id
    current.mkdir(parents=True)
    (paths.serving / "CURRENT").write_text(run_id)
    (current / "report.json").write_text(json.dumps({"run_id": run_id, "synthetic": True}))
    with duckdb.connect(str(current / "analytics.duckdb")) as conn:
        conn.execute("""
            CREATE TABLE mart_fleet AS SELECT 'EV-001' AS vehicle_id, 'Austin' AS region,
            DATE '2026-10-01' AS event_date, 2 AS trip_count, 100.0 AS distance_km,
            20.0 AS consumed_kwh, 25.0 AS charged_kwh, 8.0 AS operating_cost_usd,
            1 AS alert_count, 51.0 AS last_soc_pct, 46.0 AS max_battery_temp_c
        """)
        conn.execute("""
            CREATE TABLE fact_trip AS SELECT 'trip-1' AS event_id, 'EV-001' AS vehicle_id,
            DATE '2026-10-01' AS date_key, TIMESTAMP '2026-10-01 08:00:00' AS event_ts,
            'Austin' AS region, 'R-01' AS route_id, 50.0 AS distance_km,
            60.0 AS duration_min, 10.0 AS energy_kwh
        """)
    return TestClient(create_app(paths))


def test_health_and_no_data(paths):
    client = TestClient(create_app(paths))
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").status_code == 503
    assert client.get("/api/overview").status_code == 503
    assert client.get("/").status_code == 200


def test_snapshot_metrics_and_trace(client):
    response = client.get("/api/overview")
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["vehicles"] == 1
    assert summary["kwh_per_100km"] == 20
    assert summary["cost_usd"] == 8
    assert response.headers["X-Request-ID"]
    assert client.get("/ready").status_code == 200


def test_region_is_bounded_and_parameterized(client):
    assert client.get("/api/overview?region=Austin").json()["summary"]["vehicles"] == 1
    assert client.get("/api/overview?region=Denver").json()["summary"]["vehicles"] == 0
    assert client.get("/api/overview", params={"region": "Austin' OR 1=1--"}).status_code == 422


def test_vehicle_lookup_and_unknown_vehicle(client):
    assert len(client.get("/api/vehicles/EV-001/trips").json()["trips"]) == 1
    assert client.get("/api/vehicles/EV-999/trips").status_code == 404
    assert client.get("/api/vehicles/invalid/trips").status_code == 422


def test_read_only_surface(client):
    assert client.post("/api/overview", json={"sql": "DROP TABLE mart_fleet"}).status_code == 405
    assert client.get("/api/overview").status_code == 200


def test_invalid_pointer_fails_closed(paths):
    paths.serving.mkdir(parents=True)
    (paths.serving / "CURRENT").write_text("../../secret")
    assert TestClient(create_app(paths)).get("/ready").status_code == 503
