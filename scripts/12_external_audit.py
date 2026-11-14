"""Audit an authorized, locally prepared external ICU extract.

The input must be an hourly CSV or Parquet table with canonical column names:
patient_id, hour, and any PhysioNet-2019 compatible vital/lab columns.
It must not contain labels, treatment/order features, or protected raw data in
the repository. This script is intentionally an audit gate, not a downloader.

Example:
  python scripts/12_external_audit.py --source eicu --input /secure/eicu/hourly.parquet \
      --report outputs/external/eicu_audit.json
"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.external_data import cohort_coverage_table, require_clean_external_contract, validate_canonical_hourly


def load(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".parquet", ".pq"):
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError("input must be .parquet, .pq, or .csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=("eicu", "mimiciv", "hirid"), required=True)
    ap.add_argument("--input", type=Path, required=True,
                    help="authorized local canonical extract; never commit it")
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    audit = validate_canonical_hourly(load(args.input), args.source)
    require_clean_external_contract(audit)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    report = asdict(audit)
    report["contract"] = "pass"
    args.report.write_text(json.dumps(report, indent=2))
    cohort_coverage_table(audit).to_csv(args.report.with_suffix(".coverage.csv"), index=False)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
