import json

import duckdb
import pytest
from fastapi.testclient import TestClient
from pyspark.sql import functions as F

from fleet.api import create_app
from fleet.generate import generate, write_lines
from fleet.pipeline import build_silver, classify, ingest, run_pipeline

pytestmark = pytest.mark.spark


def test_batch_stream_replay_corrections_and_publication(spark, paths):
    expected = generate(paths, 6, 4)
    report = run_pipeline(spark, paths)
    assert report["silver_events"] == expected["expected_silver_events"]
    assert report["quarantined"] == 5
    assert report["superseded_revisions"] == 1
    assert report["bronze_unique_payloads"] == expected["raw_lines"] - 3
    pointer = (paths.serving / "CURRENT").read_text()
    with duckdb.connect(str(paths.serving / pointer / "analytics.duckdb"), read_only=True) as conn:
        assert conn.execute("SELECT count(*) FROM dim_vehicle").fetchone()[0] == 7
        regions = conn.execute("""
            SELECT DISTINCT region FROM fact_trip WHERE vehicle_id = 'EV-004' ORDER BY region
        """).fetchall()
        assert regions == [("Austin",), ("Denver",)]
        first = conn.execute("SELECT sum(distance_km) FROM fact_trip").fetchone()[0]
        second = conn.execute("SELECT sum(distance_km) FROM mart_fleet").fetchone()[0]
        assert first == pytest.approx(second)
    response = TestClient(create_app(paths)).get("/api/overview")
    assert response.status_code == 200
    assert response.json()["summary"]["vehicles"] == 6
    # File micro-batches use a new checkpoint but re-ingest identical source files safely.
    ingest(spark, paths, "stream")
    before = spark.read.format("delta").load(paths.table("bronze", "events")).count()
    assert before == report["bronze_unique_payloads"]
    ingest(spark, paths, "stream")
    assert spark.read.format("delta").load(paths.table("bronze", "events")).count() == before
    # A late, higher revision reaches the same stream after its checkpoint has advanced.
    corrected = None
    for file in paths.landing.glob("*.jsonl"):
        for line in file.read_text().splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("revision") == 2:
                corrected = {**event, "revision": 3, "distance_km": 99.0}
    assert corrected
    write_lines(paths.landing / "batch-late.jsonl", [corrected])
    ingest(spark, paths, "stream")
    new_report = build_silver(spark, paths)
    assert new_report["silver_events"] == report["silver_events"]
    silver = spark.read.format("delta").load(paths.table("silver", "events"))
    assert silver.filter(F.col("event_id") == corrected["event_id"]).first().distance_km == 99
    # Intermediate table writes never change the serving pointer; publishing is explicit.
    assert (paths.serving / "CURRENT").read_text() == pointer
    # A burst of invalid payloads fails the quality gate and preserves the published snapshot.
    invalid = [{**corrected, "event_id": f"bad-late-{i}", "distance_km": -1} for i in range(40)]
    write_lines(paths.landing / "batch-invalid.jsonl", invalid)
    ingest(spark, paths, "batch")
    with pytest.raises(ValueError, match="Quality gate failed"):
        build_silver(spark, paths)
    assert (paths.serving / "CURRENT").read_text() == pointer
    spark.catalog.clearCache()


@pytest.mark.parametrize("ansi", ["false", "true"])
def test_data_quality_and_schema_contract(spark, ansi):
    spark.conf.set("spark.sql.ansi.enabled", ansi)
    base = {
        "event_id": "test-1",
        "vehicle_id": "EV-001",
        "event_type": "telemetry",
        "schema_version": 1,
        "revision": 1,
        "event_time": "2026-10-01T08:00:00Z",
        "latitude": 30.0,
        "longitude": -97.0,
        "speed_kph": 40.0,
        "soc_pct": 50.0,
        "battery_temp_c": 33.0,
    }
    examples = [
        base,
        {**base, "soc_pct": -1},
        {**base, "latitude": 91},
        {**base, "schema_version": 2},
        {**base, "speed_kph": float("nan")},
        {**base, "event_time": "not-a-time"},
        {**base, "new_sensor": 1},
    ]
    frame = spark.createDataFrame(
        [(str(i), json.dumps(row)) for i, row in enumerate(examples)],
        "record_id string, raw_json string",
    )
    result = classify(frame.withColumn("ingested_at", F.current_timestamp())).orderBy("record_id")
    errors = [row.errors for row in result.select("record_id", "errors").collect()]
    assert errors[0] == [] and errors[6] == []
    for index in range(1, 6):
        assert errors[index]

    spark.conf.set("spark.sql.ansi.enabled", "false")


def test_bad_reference_stops_publication(spark, paths):
    generate(paths, 6, 4)
    rows = [json.loads(line) for line in paths.reference.read_text().splitlines()]
    rows.append({**rows[0], "vehicle_sk": "overlap"})
    write_lines(paths.reference, rows)
    with pytest.raises(ValueError, match="overlapping"):
        build_silver(spark, paths)
    assert not (paths.serving / "CURRENT").exists()
