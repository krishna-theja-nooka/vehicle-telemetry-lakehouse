# Operations runbook

## Process healthy, data unavailable

`/health` checks the API process. `/ready` checks a published analytics snapshot. A new installation returns 503 from `/ready` until `fleet generate` and `fleet run` succeed. Check `fleet status`, the terminal output, and the selected `FLEET_HOME`. The dashboard and CLI must use the same data root.

## Java gateway / Maven failures

Confirm `java -version` is Java 17 and Python is 3.12. First-run Delta dependencies resolve from Maven and require network access. Enterprise proxies may need JVM proxy settings. For restricted environments, set `FLEET_SPARK_JARS` to comma-separated absolute paths of trusted, compatible Delta Spark 3.3.2, Delta Storage 3.3.2 and ANTLR runtime 4.9.3 jars. Kafka mode also needs the Spark 3.5.3 Kafka connector and its transitive dependencies. Do not mix Scala 2.12 and 2.13 artifacts.

## Memory or slow processing

The default driver heap is 2 GB; allow at least 8 GB system memory. Set `SPARK_DRIVER_MEMORY=3g` before starting Spark if needed, or generate fewer vehicles into a new home. Ephemeral checkpoints prevent repeated expansion of the validation query plan. Synthetic row counts are small, so Spark startup and transaction metadata dominate total runtime; do not extrapolate throughput from this demo.

## Quality gate fails

Read `silver/quarantine` as Delta to inspect the original payload and error array. Fix the source contract, dimensions, or event revision and add a new immutable landing file; do not rewrite consumed files. Use a higher revision for changed event values. An unknown schema needs an intentional reviewed parser update. Do not lower quality thresholds merely to make an unexplained failure green.

## Streaming restart / broker loss

Keep `data/checkpoints/stream` or `data/checkpoints/kafka`. `availableNow` drains available input and terminates successfully. Restart it to process new files/messages. Do not overwrite existing landing files. Kafka offsets are stored in the checkpoint; `failOnDataLoss=true` makes missing offsets visible. Bronze content-hash merge tolerates replay, but deleting checkpoints is still an operator decision with possible large backfills.

## Pipeline fails after some Delta writes

The existing dashboard pointer remains unchanged. Inspect the failed run's dbt log and results under `data/serving/<run-id>`. Rerun `fleet run`; immutable Bronze and deterministic transformations allow recovery. The local lock is released when the writer process exits. Never manually edit the published database while the API serves it.

## Retention and backups

Back up the data root and its checkpoints consistently while the pipeline is stopped. Keep old serving snapshots while readers might still use them. Local cleanup and Delta VACUUM are deliberately not automatic; choose retention for real workloads and avoid vacuuming files needed for time travel. The example GCP resources use a 30-day lifecycle and are only for synthetic demos.

## Public hosting boundary

The app binds to localhost by default and Docker publishes to `127.0.0.1`. Before public hosting add identity/authorization, HTTPS, explicit host configuration, request limiting, monitoring, managed credentials, backup and privacy policies. Cloud pipeline tasks and the dashboard are separate deployments.
