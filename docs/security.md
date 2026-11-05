# Security and privacy

Only generated vehicle IDs, fictional model names, synthetic GPS coordinates and fabricated operational records are used. Do not upload employer/customer telemetry, VINs, driver identities, contracts or API keys to this repository.

The dashboard API is read-only. Region values are allowlisted, vehicle identifiers are bounded, SQL values are parameterized, and the client cannot submit SQL. The serving pointer is format-checked before opening a path. DuckDB is opened read-only against an immutable published snapshot. UI text uses DOM text nodes; the dashboard sets a restrictive Content Security Policy and does not load third-party scripts. Swagger's documentation page uses its standard external assets.

The local pipeline trusts its operator-controlled file paths and dependencies. It is not an untrusted public ingestion endpoint and has no authentication layer. Delta and DuckDB files are not encrypted by the application. The example Kafka broker uses plaintext localhost networking and synthetic data only. Do not expose it to the internet.

Cloud samples use existing authenticated CLI/application-default credentials. No private key files are committed. Use least-privilege cloud roles, a secrets manager, private networking and workload identities for deployment. The Terraform bucket enforces uniform access and public-access prevention; it does not configure a complete organization-level IAM or networking design.

Report security issues privately to the repository owner rather than posting credentials or sensitive payloads in issues. Dependency pins make builds repeatable but still require periodic upgrade and security review.
