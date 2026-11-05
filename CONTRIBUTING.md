# Contributing

Use Python 3.12 and Java 17. Install `requirements.lock` and the package in editable mode from the repository root. Use synthetic data only.

Before proposing a change, run Ruff and pytest as documented in the README. Changes to event fields, correction ordering, SCD2 intervals or metrics need a relevant regression test and a data-contract update. Keep runtime evidence separate from targets. Do not commit generated lakehouse files, virtual environments, Terraform state or secrets.

For substantial changes, describe the operational problem, the proposed behavior, validation, and any migration implications. Update dependency pins deliberately and check Spark/Delta compatibility before upgrading either package.
