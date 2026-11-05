import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from delta.tables import DeltaTable
from filelock import FileLock
from pyspark.sql import Window
from pyspark.sql import functions as F
from pyspark.sql import types as T

from fleet.config import Paths

EVENT_SCHEMA = T.StructType(
    [
        T.StructField(name, dtype, True)
        for name, dtype in [
            ("event_id", T.StringType()),
            ("vehicle_id", T.StringType()),
            ("event_type", T.StringType()),
            ("schema_version", T.IntegerType()),
            ("revision", T.IntegerType()),
            ("event_time", T.StringType()),
            ("emitted_at", T.StringType()),
            ("latitude", T.DoubleType()),
            ("longitude", T.DoubleType()),
            ("speed_kph", T.DoubleType()),
            ("soc_pct", T.DoubleType()),
            ("battery_temp_c", T.DoubleType()),
            ("distance_km", T.DoubleType()),
            ("duration_min", T.DoubleType()),
            ("energy_kwh", T.DoubleType()),
            ("cost_usd", T.DoubleType()),
            ("route_id", T.StringType()),
            ("severity", T.StringType()),
            ("code", T.StringType()),
            ("_corrupt_record", T.StringType()),
        ]
    ]
)
GOLD_TABLES = [
    "dim_vehicle",
    "dim_date",
    "fact_trip",
    "fact_charging",
    "fact_maintenance",
    "fact_toll",
    "fleet_daily",
]


def merge_bronze(spark, frame, paths: Paths):
    rows = (
        frame.select(F.col("value").alias("raw_json"))
        .withColumn("record_id", F.sha2("raw_json", 256))
        .dropDuplicates(["record_id"])
        .withColumn("ingested_at", F.current_timestamp())
    )
    target = paths.table("bronze", "events")
    if DeltaTable.isDeltaTable(spark, target):
        (
            DeltaTable.forPath(spark, target)
            .alias("t")
            .merge(rows.alias("s"), "t.record_id = s.record_id")
            .whenNotMatchedInsertAll()
            .execute()
        )
    else:
        rows.write.format("delta").mode("errorifexists").save(target)


def ingest(spark, paths: Paths, mode: str = "batch", kafka_servers: str | None = None):
    """Ingest bounded batch or checkpointed available-now micro-batches into Bronze."""
    if mode == "batch":
        merge_bronze(spark, spark.read.text(str(paths.landing / "*.jsonl")), paths)
        return
    if mode == "kafka":
        if not kafka_servers:
            raise ValueError("Kafka mode requires --bootstrap-servers.")
        reader = (
            spark.readStream.format("kafka")
            .option("kafka.bootstrap.servers", kafka_servers)
            .option("subscribe", "fleet.telemetry")
            .option("startingOffsets", "earliest")
            .option("failOnDataLoss", "true")
        )
        frame = reader.load().selectExpr("CAST(value AS STRING) AS value")
    else:
        frame = (
            spark.readStream.format("text")
            .option("maxFilesPerTrigger", 1)
            .option("pathGlobFilter", "*.jsonl")
            .load(str(paths.landing))
        )
    checkpoint = str(paths.root / "checkpoints" / mode)
    query = (
        frame.writeStream.foreachBatch(lambda batch, _: merge_bronze(spark, batch, paths))
        .option("checkpointLocation", checkpoint)
        .trigger(availableNow=True)
        .start()
    )
    query.awaitTermination()


def range_ok(name, low, high):
    return F.col(name).isNotNull() & F.col(name).between(low, high) & ~F.isnan(name)


def classify(frame):
    """Vectorized checks. Preserve original JSON for rejected/unknown schema records."""
    parsed = (
        frame.withColumn("data", F.from_json("raw_json", EVENT_SCHEMA))
        .select("record_id", "raw_json", "ingested_at", "data.*")
        .withColumn("event_ts", F.try_to_timestamp("event_time"))
    )
    required = (
        F.col("event_id").rlike(r"^[A-Za-z0-9_-]{1,100}$")
        & F.col("vehicle_id").rlike(r"^EV-[0-9]{3,4}$")
        & F.col("revision").between(1, 10000)
        & F.col("event_type").isin("telemetry", "trip", "charging", "maintenance", "toll")
    )
    time_ok = (
        F.col("event_time").rlike(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        & F.col("event_ts").isNotNull()
        & (F.col("event_ts") <= F.col("ingested_at") + F.expr("INTERVAL 1 DAY"))
    )
    telemetry_ok = (
        range_ok("latitude", -90, 90)
        & range_ok("longitude", -180, 180)
        & range_ok("speed_kph", 0, 250)
        & range_ok("soc_pct", 0, 100)
        & range_ok("battery_temp_c", -40, 90)
    )
    trip_ok = (
        range_ok("distance_km", 0.01, 2000)
        & range_ok("duration_min", 0.01, 1440)
        & range_ok("energy_kwh", 0, 500)
        & F.col("route_id").rlike(r"^R-[0-9]{2}$")
    )
    charge_ok = (
        range_ok("energy_kwh", 0.01, 500)
        & range_ok("duration_min", 0.01, 1440)
        & range_ok("cost_usd", 0, 10000)
    )
    maintenance_ok = (
        range_ok("cost_usd", 0, 100000)
        & F.col("severity").isin("info", "warning", "critical")
        & F.col("code").rlike(r"^[A-Z0-9-]{1,40}$")
    )
    rules = {
        "malformed_json": F.col("_corrupt_record").isNull() & F.col("event_id").isNotNull(),
        "invalid_identity": required,
        "unsupported_schema": F.col("schema_version") == 1,
        "invalid_event_time": time_ok,
        "invalid_telemetry": (F.col("event_type") != "telemetry") | telemetry_ok,
        "invalid_trip": (F.col("event_type") != "trip") | trip_ok,
        "invalid_charge": (F.col("event_type") != "charging") | charge_ok,
        "invalid_maintenance": (F.col("event_type") != "maintenance") | maintenance_ok,
        "invalid_toll": (F.col("event_type") != "toll") | range_ok("cost_usd", 0, 1000),
    }
    errors = [F.when(~F.coalesce(ok, F.lit(False)), F.lit(label)) for label, ok in rules.items()]
    return parsed.withColumn("errors", F.filter(F.array(*errors), lambda x: x.isNotNull()))


def write_delta(frame, path):
    frame.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(path)


def build_silver(spark, paths: Paths) -> dict:
    dimension = (
        spark.read.json(str(paths.reference))
        .withColumn("valid_from", F.try_to_timestamp("valid_from"))
        .withColumn("valid_to", F.try_to_timestamp("valid_to"))
    )
    dimension.createOrReplaceTempView("vehicle_reference")
    bad_dimension = spark.sql("""
        SELECT a.vehicle_sk FROM vehicle_reference a JOIN vehicle_reference b
        ON a.vehicle_id = b.vehicle_id AND a.vehicle_sk != b.vehicle_sk
        AND a.valid_from < b.valid_to AND b.valid_from < a.valid_to
        UNION ALL
        SELECT vehicle_sk FROM vehicle_reference GROUP BY vehicle_sk HAVING count(*) > 1
        UNION ALL
        SELECT vehicle_sk FROM vehicle_reference
        WHERE valid_from IS NULL OR valid_to IS NULL OR valid_from >= valid_to
           OR vehicle_sk IS NULL OR vehicle_id IS NULL OR region IS NULL
    """)
    if bad_dimension.limit(1).count():
        raise ValueError("Vehicle reference contains invalid or overlapping SCD2 intervals.")
    bronze = spark.read.format("delta").load(paths.table("bronze", "events"))
    # Materialize a short plan before branching into rejection, temporal join and deduplication.
    # These are ephemeral execution checkpoints; durable recovery always starts from Bronze.
    checked = classify(bronze).localCheckpoint(eager=True)
    good = checked.filter(F.size("errors") == 0).alias("e")
    ref = dimension.alias("d")
    joined = good.join(
        ref,
        (
            (F.col("e.vehicle_id") == F.col("d.vehicle_id"))
            & (F.col("e.event_ts") >= F.col("d.valid_from"))
            & (F.col("e.event_ts") < F.col("d.valid_to"))
        ),
        "left",
    ).select("e.*", "d.vehicle_sk", "d.region")
    rejected = (
        checked.filter(F.size("errors") > 0)
        .select("record_id", "raw_json", "errors", "ingested_at")
        .unionByName(
            joined.filter("vehicle_sk IS NULL").select(
                "record_id",
                "raw_json",
                F.array(F.lit("unknown_vehicle_version")).alias("errors"),
                "ingested_at",
            )
        )
    )
    # Stable tie-breaker; same ID/revision conflicts are reported separately below.
    eligible = joined.filter("vehicle_sk IS NOT NULL").localCheckpoint(eager=True)
    conflicts = eligible.groupBy("event_id", "revision").count().filter("count > 1").count()
    if conflicts:
        raise ValueError("Conflicting payloads share an event ID and revision; fix at the source.")
    window = Window.partitionBy("event_id").orderBy(F.desc("revision"), F.desc("record_id"))
    clean = (
        eligible.withColumn("rn", F.row_number().over(window))
        .filter("rn = 1")
        .drop("rn", "raw_json", "errors", "_corrupt_record")
        .withColumn("event_date", F.to_date("event_ts"))
    )
    write_delta(rejected, paths.table("silver", "quarantine"))
    total, invalid = bronze.count(), rejected.count()
    if total == 0 or invalid / total > 0.05:
        raise ValueError(f"Quality gate failed: {invalid}/{total} rejected (maximum 5%).")
    write_delta(clean, paths.table("silver", "events"))
    write_delta(dimension, paths.table("gold", "dim_vehicle"))
    accepted = clean.count()
    checked.unpersist()
    eligible.unpersist()
    return {
        "bronze_unique_payloads": total,
        "quarantined": invalid,
        "silver_events": accepted,
        "superseded_revisions": total - invalid - accepted,
        "quality_pass_pct": round((total - invalid) / total * 100, 3),
    }


def build_gold(spark, paths: Paths):
    spark.read.format("delta").load(paths.table("silver", "events")).createOrReplaceTempView(
        "events"
    )
    for name in GOLD_TABLES[1:]:
        sql = (Path(__file__).parent / "sql" / f"{name}.sql").read_text()
        write_delta(spark.sql(sql), paths.table("gold", name))


def build_serving(spark, paths: Paths, report: dict, run_id: str) -> Path:
    snapshot = paths.serving / run_id
    snapshot.mkdir(parents=True)
    for table in GOLD_TABLES:
        (
            spark.read.format("delta")
            .load(paths.table("gold", table))
            .coalesce(1)
            .write.mode("errorifexists")
            .parquet(str(snapshot / "exports" / table))
        )
    env = {
        **os.environ,
        "FLEET_DB": str(snapshot / "analytics.duckdb"),
        "FLEET_EXPORTS": (snapshot / "exports").as_posix(),
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
        "DBT_LOG_PATH": str(snapshot / "logs"),
    }
    dbt_project = Path(os.getenv("FLEET_DBT_PROJECT", "dbt")).resolve()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dbt.cli.main",
            "build",
            "--project-dir",
            str(dbt_project),
            "--profiles-dir",
            str(dbt_project),
            "--target-path",
            str(snapshot / "dbt"),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    (snapshot / "dbt.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"dbt validation failed; see {snapshot / 'dbt.log'}")
    report["delta_versions"] = {
        table: DeltaTable.forPath(spark, paths.table("gold", table))
        .history(1)
        .select("version")
        .first()[0]
        for table in GOLD_TABLES
    }
    return snapshot


def run_pipeline(spark, paths: Paths, mode="batch", kafka_servers=None) -> dict:
    paths.root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8]
    # Only one local writer. The dashboard reads immutable published DuckDB snapshots.
    with FileLock(str(paths.root / "pipeline.lock"), timeout=0):
        ingest(spark, paths, mode, kafka_servers)
        report = build_silver(spark, paths)
        build_gold(spark, paths)
        report.update(run_id=run_id, mode=mode, synthetic=True)
        snapshot = build_serving(spark, paths, report, run_id)
        report["duration_seconds"] = round(time.perf_counter() - started, 2)
        report["published_at"] = datetime.now(UTC).isoformat()
        (snapshot / "report.json").write_text(json.dumps(report, indent=2))
        pointer = paths.serving / "CURRENT.tmp"
        pointer.write_text(run_id)
        pointer.replace(paths.serving / "CURRENT")
    print(json.dumps({"event": "pipeline_published", **report}))
    return report
