## Fleet Pulse v0.1.0

Initial release of a synthetic EV telemetry lakehouse and interactive fleet analytics dashboard.

### Included
- PySpark and real Delta Lake Bronze/Silver/Gold tables.
- Batch and checkpointed file streaming; optional Kafka adapter.
- Duplicate handling, event revisions, late corrections, quarantine and SCD2 vehicle history.
- Seven dbt models and 32 data tests.
- Region filters, energy charts, vehicle search, trip detail and CSV export.
- Run reports, request IDs, immutable serving snapshots and atomic publication.
- Docker, GitHub Actions and optional cloud integration examples.

### Observed local validation
- 17 pytest cases passed, including real Spark/Delta streaming integration.
- 32 dbt tests passed.
- Default dataset: 2,898 input lines, 2,895 unique Bronze payloads, five rejected records, 2,889 canonical events and 504 trips.
- Desktop/mobile dashboard interactions tested against the running API.

All data and outcomes are synthetic. Kafka and cloud deployment examples require environment-specific acceptance tests. The release workflow checks container process health, not a full pipeline inside Docker.

### Downloads
The source ZIP is the complete project. The Python wheel contains application code and UI resources; use the source project for dbt configuration and deployment files. The container is published to the repository's GitHub Container Registry package using the release version tag.
