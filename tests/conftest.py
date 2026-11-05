import json

import duckdb
import pytest
from fastapi.testclient import TestClient

from fleet.api import create_app
from fleet.config import Paths, spark_session


@pytest.fixture(scope="session")
def spark():
    session = spark_session()
    yield session
    session.stop()


@pytest.fixture
def paths(tmp_path):
    return Paths(tmp_path)


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
