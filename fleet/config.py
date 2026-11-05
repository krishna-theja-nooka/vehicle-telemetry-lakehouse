import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    root: Path

    @classmethod
    def from_env(cls):
        return cls(Path(os.getenv("FLEET_HOME", "data")).resolve())

    def table(self, layer: str, name: str) -> str:
        return str(self.root / "lakehouse" / layer / name)

    @property
    def landing(self) -> Path:
        return self.root / "landing"

    @property
    def reference(self) -> Path:
        return self.root / "reference" / "vehicles.jsonl"

    @property
    def serving(self) -> Path:
        return self.root / "serving"


def spark_session(kafka: bool = False):
    from delta import configure_spark_with_delta_pip
    from pyspark.sql import SparkSession

    # Databricks supplies its own Spark/Delta runtime; do not replace it with local jars.
    if os.getenv("DATABRICKS_RUNTIME_VERSION"):
        return SparkSession.builder.getOrCreate()
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    builder = (
        SparkSession.builder.appName("fleet-telemetry-lakehouse")
        .master(os.getenv("SPARK_MASTER", "local[2]"))
        .config("spark.driver.memory", os.getenv("SPARK_DRIVER_MEMORY", "2g"))
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog"
        )
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.databricks.delta.snapshotPartitions", "2")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.streaming.forceDeleteTempCheckpointLocation", "false")
    )
    packages = ["org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3"] if kafka else []
    local_jars = os.getenv("FLEET_SPARK_JARS")
    if local_jars:
        # Optional pre-provisioned Delta/Kafka jars for offline or proxied environments.
        spark = builder.config("spark.jars", local_jars).getOrCreate()
    else:
        spark = configure_spark_with_delta_pip(builder, extra_packages=packages).getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark
