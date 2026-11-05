# Optional integrations

The default build requires none of these services. The local Spark/Delta/file-stream/dbt/API path is the verified reference. These integration examples need separate credentials/infrastructure and an acceptance run in your environment. Do not describe a supplied configuration as a completed cloud deployment.

## Kafka

Start the local single-node KRaft broker with Docker. This listener is intended for a producer and Spark running on the host, not another container:

```bash
docker compose --profile kafka up -d kafka
python -m pip install kafka-python==2.2.10
python scripts/produce_kafka.py --landing data/landing
fleet run --mode kafka --bootstrap-servers localhost:9092
```

Generate the reference data before publishing. The producer sends all JSONL, including intentional bad records, to `fleet.telemetry`; acknowledgements use `acks=all`. Spark uses its official Kafka source and stores offsets under `checkpoints/kafka`. It downloads the Spark 3.5.3 Scala 2.12 Kafka connector on first use. The finite `availableNow` trigger exits after draining available messages. Rerun it for new messages. Local plaintext networking is for synthetic development only; use TLS/SASL and managed credentials for real deployments.

Do not point the same checkpoint at a recreated topic with unrelated offsets. Retain the broker and topic for resume testing, or intentionally create a new checkpoint/data home for a fresh demo. The broker service has no durable-volume configuration and is not a production Kafka deployment.

## Databricks

`databricks.yml` declares a job with one existing cluster and `max_concurrent_runs=1`. The job runs the same Bronze/Silver/Gold functions. It uses an existing Unity Catalog Volume; it does not provision a workspace, cluster, identity, or dashboard. Use a Spark 3.5-compatible Databricks runtime and the runtime's bundled Delta implementation. Do not install the local pinned PySpark package over the managed runtime.

After authenticating the Databricks CLI, set:

```bash
export BUNDLE_VAR_cluster_id='YOUR_EXISTING_CLUSTER_ID'
export BUNDLE_VAR_lakehouse_root='/Volumes/YOUR_CATALOG/YOUR_SCHEMA/YOUR_VOLUME/fleet-demo'
databricks bundle validate
databricks bundle deploy
databricks bundle run telemetry
```

Choose a synthetic-data volume you own. `--seed-demo` only generates data when reference data is absent. The job returns quality counts; inspect the Delta tables and run the equivalent warehouse/dbt checks before presenting the cloud path as validated. The local DuckDB publication step is deliberately separate because database files on a remote volume have different locking and filesystem semantics.

[Databricks bundle documentation](https://docs.databricks.com/aws/en/dev-tools/bundles/settings)

## BigQuery and Terraform

`deploy/gcp/main.tf` defines a private Cloud Storage bucket and a BigQuery dataset, both scoped to your supplied project/location. Objects/tables have a 30-day demo lifecycle. The configuration does not grant broad IAM roles. Enable the required APIs and authenticate with your organization's approved method.

```bash
cd deploy/gcp
terraform init
terraform fmt
terraform validate
terraform plan -var='project_id=YOUR_PROJECT' -var='bucket_name=YOUR_UNIQUE_BUCKET'
```

Review the plan and costs before applying it yourself. No cloud resources were created while building this project. To load **one** coalesced `fact_trip` Parquet export from a published local snapshot:

```bash
python -m pip install google-cloud-bigquery==3.31.0
python deploy/gcp/load_bigquery.py --table YOUR_PROJECT.synthetic_fleet.fact_trip --parquet /absolute/path/to/part-00000.parquet
```

Use Application Default Credentials. The loader uses `WRITE_EMPTY`, so it will not overwrite an existing nonempty table. This is an explicit one-time load, not CDC synchronization. Keep the data location compatible with your dataset. Managed infrastructure/storage/querying may incur costs.

## Snowflake

Use an existing Snowflake warehouse/database and a restricted role, then execute `deploy/snowflake/load.sql` with SnowSQL. The script creates a demo schema, Parquet format, internal stage and typed trip fact table, loads one export, and queries distance-weighted efficiency.

```bash
snowsql -D file_path=/absolute/path/to/part-00000.parquet -f deploy/snowflake/load.sql
```

The stage is exclusively for `fact_trip` Parquet files. Treat this as a first-load example: Snowflake file-load history can suppress repeated files, but new export filenames can duplicate rows. Incremental updates require a staging table plus an event-ID/revision-aware `MERGE`, which is not implemented by this example. No Snowflake credentials or consumption are required for the local project.

[Snowflake COPY documentation](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table)

## MLflow

Optionally track local pipeline runtime and quality metrics:

```bash
python -m pip install mlflow==2.22.0
python scripts/track_run.py --home data
mlflow ui --backend-store-uri data/mlruns --host 127.0.0.1 --port 5000
```

Use a separate environment for optional integrations if dependency resolution conflicts with the core lockfile. The tracking script logs one pipeline run report. It does not train a predictive maintenance model or claim model accuracy; measured battery/alert metrics are deterministic synthetic analytics.
