# Architecture and decisions

## Local boundaries

1. The generator writes immutable JSONL files through a temporary-file rename. A failed generation is never presented as a complete file to Spark.
2. Batch and streaming adapters pass raw strings to the same Bronze sink. SHA-256 of the exact raw payload makes transport replay idempotent. Bronze merge is insert-only.
3. Silver parses the explicit schema, records errors, resolves vehicle history and selects the highest valid revision. Unknown optional fields remain recoverable in Bronze. Unknown schema versions go to quarantine.
4. Gold Spark SQL creates dimensions, facts and a daily aggregate. Facts join the vehicle version effective at **event time**, using `[valid_from, valid_to)` intervals. Overlaps fail validation before analytics publication.
5. A run-specific Parquet export is materialized and tested by dbt into a new DuckDB database. Only a complete, passing run replaces the `CURRENT` pointer using an atomic local rename.
6. API requests resolve that pointer once and open the immutable database read-only. A refresh sees either the old complete snapshot or the new one. Do not mutate published snapshot files.

## ADR 001 — Spark and Delta

Use Spark 3.5.3 and Delta 3.3.2 as an explicit compatible pair. Java 17 and Python 3.12 are the local target. These are pinned for reproducibility, not advertised as the newest releases. Delta transaction logs are actual output, not simulated with JSON/SQLite. Python package installation does not bundle the Delta JVM jars: Maven access or pre-provisioned jars is needed.

## ADR 002 — Bounded recomputation

Silver/Gold recompute from the retained Bronze history. This makes late corrections and historical region assignments deterministic at portfolio scale. It costs more than incremental partition processing. No claim of unbounded, low-latency event-time analytics is made. Ephemeral execution checkpoints shorten the Spark query plan; restart durability comes from Delta Bronze and source checkpoints, not those in-memory execution checkpoints.

## ADR 003 — SCD2 and revision policy

The vehicle reference is a supplied synthetic SCD2 history, not an implemented CDC feed. Version keys are stable, intervals cannot overlap, and historical facts use the appropriate version. A correction needs a higher integer revision. Different payloads at the same event ID and revision stop publication rather than guessing which is authoritative. Invalid higher revisions are quarantined; the last valid revision remains eligible.

## ADR 004 — Serving publication

Delta's atomicity is per table. A local writer lock serializes pipeline runs and a separate atomic snapshot pointer protects dashboard consumers from partial multi-table refreshes. The API never uses the lock to block readers. Failed runs can leave newer Delta versions and incomplete staging exports, but they cannot advertise an incomplete dashboard snapshot. Rerun to recover; preserve old published snapshots until readers have finished.

## ADR 005 — DuckDB and dbt

DuckDB avoids cloud costs and serves compact local analytics without a running database service. Spark computes the medallion tables; dbt makes relational checks and the semantic metric layer inspectable. Gold tables export to Parquet before dbt reads them. The dashboard is served by FastAPI with small static HTML/CSS/JavaScript files and no third-party frontend CDN.

## Scaling plan

Partition large telemetry tables by event date, track affected dates for corrections, compact small files, and replace full-history rebuilds with tested incremental logic. Move the writer lock/orchestration and publication manifest to shared services before adding multiple workers. Define retention and watermark policies against customer latency requirements. Add a catalog, RBAC, PII classification, service-level monitoring and managed Kafka credentials before consuming real fleet data.

## References

- [Delta/Spark compatibility](https://docs.delta.io/releases/)
- [Delta merge and idempotent streaming guidance](https://docs.delta.io/delta-update/)
- [Spark Structured Streaming semantics](https://spark.apache.org/docs/3.5.3/structured-streaming-programming-guide.html)
- [dbt DuckDB profile](https://docs.getdbt.com/docs/local/connect-data-platform/duckdb-setup)
