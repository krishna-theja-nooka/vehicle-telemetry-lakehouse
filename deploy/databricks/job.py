"""Databricks job: medallion tables on an existing Unity Catalog Volume.

Cloud execution is optional; this path does not publish the local DuckDB dashboard.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fleet.config import Paths, spark_session  # noqa: E402
from fleet.generate import generate  # noqa: E402
from fleet.pipeline import build_gold, build_silver, ingest  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--home", required=True)
parser.add_argument("--seed-demo", action="store_true")
args = parser.parse_args()
if not args.home.startswith("/Volumes/"):
    raise ValueError(
        "Use an existing Unity Catalog Volume path: /Volumes/catalog/schema/volume/..."
    )
paths = Paths(Path(args.home))
spark = spark_session()
spark.conf.set("spark.sql.session.timeZone", "UTC")
if args.seed_demo and not paths.reference.exists():
    generate(paths)
ingest(spark, paths, "batch")
report = build_silver(spark, paths)
build_gold(spark, paths)
print(json.dumps({"cloud_medallion_complete": True, **report}))
