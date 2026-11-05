# Validation evidence

The local build was validated on Linux with Python 3.12, Java 17, Spark 3.5.3, Delta 3.3.2, DuckDB 1.3.2 and dbt Core 1.9.4. These are observed results from synthetic data, not deployment or business-impact claims.

| Check | Observed result |
| --- | --- |
| Pytest | 17 passed, including four real Spark integration test cases |
| dbt | Seven models built; 32 data tests passed |
| Ruff lint and formatting | Passed |
| Clean dependency installation | Complete lockfile installed into a fresh virtual environment; `pip check` and all 17 tests passed |
| Default batch ingestion | 2,898 input lines → 2,895 unique Bronze payloads |
| Validation | Five quarantined records; one superseded valid revision |
| Canonical Silver | 2,889 events |
| Fleet analytics | 24 vehicles, 504 trips, 26,069.69 km, 5,600.784 trip kWh |
| Recorded synthetic costs | USD 5,787.60 (charging + maintenance + tolls) |
| Observed batch pipeline duration | 50.44 seconds, excluding Spark JVM startup; not a scale benchmark |
| Streaming | Real file micro-batches, checkpoint restart, replay deduplication and a later correction passed |
| Failure recovery | Excess invalid records blocked publication and preserved the previous serving pointer |
| SCD2 | EV-004 facts attributed to Austin before the transfer and Denver after it |
| Browser | Desktop 1440px and mobile 390px; region filter, vehicle search, 21-trip drill-down and CSV download passed; no page errors or document overflow |
| Kafka broker path | Implemented, not executed against a broker in this build environment |
| Docker / native Windows | Supplied configuration; not executed in this build environment |
| Databricks, Snowflake, BigQuery, Terraform | Optional source/configuration examples; no cloud deployment or credentialed acceptance test performed |
| MLflow extension | Tracking script provided; optional MLflow environment not exercised |

Evidence files: [sample run](../reports/sample-run.json), [JUnit results](../reports/pytest.xml), and [generator manifest](../examples/generator-manifest.json). The sample report preserves the observed pipeline run ID and Gold Delta versions. It lists each dbt node's actual status.

The first full run exposed excessive Spark query-plan expansion. Materializing short execution plans before the temporal-join/deduplication branches resolved it, and the default driver heap is now explicitly 2 GB. This is reflected in the tested source.

The environment required Delta jars to be downloaded from official Maven artifacts and passed through `FLEET_SPARK_JARS` because the JVM's default resolver could not reach Maven directly. Actual Spark/Delta execution was used; no fake Delta engine or mocked streaming sink replaced it. The standard Maven resolver path still needs network access on your machine and in GitHub Actions.

A Starlette/AnyIO deprecation warning is emitted by the pinned test stack. The tests pass; dependency upgrades should be reviewed together. GitHub Actions results will be available after you publish the repository. No green badge or hosted service is asserted before that run.
