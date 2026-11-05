import argparse
import json

from fleet.config import Paths, spark_session
from fleet.generate import generate


def main():
    parser = argparse.ArgumentParser(description="Synthetic vehicle telemetry lakehouse")
    parser.add_argument("--home", help="Data root (default FLEET_HOME or ./data)")
    commands = parser.add_subparsers(dest="command", required=True)
    seed = commands.add_parser("generate", help="Generate deterministic synthetic JSONL")
    seed.add_argument("--vehicles", type=int, default=24)
    seed.add_argument("--days", type=int, default=7)
    seed.add_argument("--seed", type=int, default=42)
    run = commands.add_parser("run", help="Ingest, validate, transform and publish dashboard data")
    run.add_argument("--mode", choices=["batch", "stream", "kafka"], default="batch")
    run.add_argument("--bootstrap-servers", default="localhost:9092")
    commands.add_parser("status", help="Print the last published run report")
    args = parser.parse_args()
    from pathlib import Path

    paths = Paths(Path(args.home).resolve()) if args.home else Paths.from_env()
    if args.command == "generate":
        print(json.dumps(generate(paths, args.vehicles, args.days, args.seed), indent=2))
    elif args.command == "status":
        pointer = paths.serving / "CURRENT"
        if not pointer.exists():
            parser.exit(1, "No published snapshot. Run fleet generate, then fleet run.\n")
        print((paths.serving / pointer.read_text().strip() / "report.json").read_text())
    else:
        from fleet.pipeline import run_pipeline

        spark = spark_session(kafka=args.mode == "kafka")
        try:
            run_pipeline(spark, paths, args.mode, args.bootstrap_servers)
        finally:
            spark.stop()


if __name__ == "__main__":
    main()
