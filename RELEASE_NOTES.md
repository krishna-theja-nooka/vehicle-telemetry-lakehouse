# Fleet Pulse v0.2.0 — Fleet Analytics Copilot

Adds **Ask Fleet Pulse**, a responsive chat panel backed by local Meta Llama 3.2 3B
through Ollama. No paid LLM API is needed.

- Validated structured tool selection with parameterized, read-only analytics.
- Fleet summaries, top-five rankings, regional comparisons, vehicle trips and quality counts.
- Answers include snapshot, reporting period, sources and request ID.
- Explicit deterministic fallback when Ollama is unavailable or returns invalid output.
- Input validation, demo rate limits, bounded retries and safety refusals.
- PowerShell instructions, optional Docker Ollama profile and API documentation.

The existing Spark/Delta/dbt lakehouse is retained. All data remains synthetic.
Tests exercise mocked Ollama responses and actual isolated DuckDB tools. Browser
checks exercise real fallback behavior against the published synthetic snapshot.
Live Llama inference and Docker Compose are not validated in the build environment.
The GitHub release workflow separately builds and smoke-tests the application container.

Model weights are governed by Meta's own license and acceptable-use terms.
