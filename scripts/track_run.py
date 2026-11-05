"""Optional local MLflow tracking of pipeline quality and runtime; no trained model claim."""

import argparse
import json
from pathlib import Path


def main():
    import mlflow

    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, default=Path("data"))
    args = parser.parse_args()
    root = args.home.resolve()
    run = (root / "serving" / "CURRENT").read_text().strip()
    report_file = root / "serving" / run / "report.json"
    report = json.loads(report_file.read_text())
    mlflow.set_tracking_uri((root / "mlruns").as_uri())
    mlflow.set_experiment("fleet-pipeline-quality")
    with mlflow.start_run(run_name=run):
        mlflow.log_params({"mode": report["mode"], "synthetic": True, "spark": "3.5.3"})
        mlflow.log_metrics(
            {
                k: report[k]
                for k in [
                    "duration_seconds",
                    "bronze_unique_payloads",
                    "silver_events",
                    "quarantined",
                    "quality_pass_pct",
                    "superseded_revisions",
                ]
            }
        )
        mlflow.log_artifact(str(report_file))
    print(f"Tracked pipeline run {run} in {root / 'mlruns'}")


if __name__ == "__main__":
    main()
