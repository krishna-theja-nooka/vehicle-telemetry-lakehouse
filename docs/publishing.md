# Publish on GitHub

Create an empty public repository called `vehicle-telemetry-lakehouse`. Upload the extracted folder's **contents** at the repository root, including `.github/workflows/ci.yml` and `.gitignore`. Do not upload `data/`, `.venv/`, credentials or generated warehouse files.

With Git:

```bash
git init
git add .
git commit -m "Build vehicle telemetry lakehouse and fleet analytics"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/vehicle-telemetry-lakehouse.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub account. The remote must exist and Git must be authenticated. The source ZIP excludes local `.git` metadata, so initialize it after extracting. The development workspace already has a local repository.

Use the About text and topics from the README. Wait for CI to pass, then run **Actions → Release and publish package → Run workflow**. It publishes the container and creates the version tag/release automatically. Do not create the same release manually first. See [GitHub setup](github-setup.md).

Suggested release notes: initial synthetic telemetry generator, real Spark/Delta batch and streaming ingestion, revision handling, SCD2 fleet models, quarantine, dbt validation, immutable analytics snapshots, FastAPI dashboard, tests and optional deployment examples. Mention that optional cloud paths need environment-specific validation.

For LinkedIn, share the repository link plus a short recording of your own run. Describe what you implemented and what you tested. Avoid claims of real customer use, production scale, manufacturer integration, predictive maintenance accuracy or measured business savings.
