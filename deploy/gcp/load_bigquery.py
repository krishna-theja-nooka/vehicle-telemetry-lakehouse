"""Load one validated Gold Parquet export through official BigQuery client/ADC."""

import argparse
import re
from pathlib import Path


def main():
    from google.cloud import bigquery

    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True, help="project.dataset.table")
    parser.add_argument("--parquet", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(
        r"[a-z][a-z0-9-]+\.[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*", args.table
    ):
        raise ValueError("Use a project.dataset.table identifier.")
    client = bigquery.Client(project=args.table.split(".")[0])
    config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_EMPTY,
    )
    with args.parquet.open("rb") as source:
        job = client.load_table_from_file(source, args.table, job_config=config)
    job.result(timeout=180)
    print(f"Loaded {job.output_rows} rows into {args.table}; existing tables are not overwritten.")


if __name__ == "__main__":
    main()
