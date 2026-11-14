"""Step 1: load both hospitals once, label, split and audit. No modelling.

    python scripts/01_audit.py            # expects data/raw/training_set{A,B}
    python scripts/01_audit.py --download # fetch from PhysioNet first

Writes data/processed/hourly.parquet and, in outputs/:
patients.csv, splits.csv, split_summary.csv, availability.csv, data_audit.csv
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src import audit, data_io, labels, splits as S  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(ROOT / "data/raw"))
    ap.add_argument("--processed", default=str(ROOT / "data/processed"))
    ap.add_argument("--out", default=str(ROOT / "outputs"))
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()
    raw, processed, out = Path(args.raw), Path(args.processed), Path(args.out)
    processed.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

    if args.download:
        data_io.download(raw)

    t0 = time.time()
    cache = processed / "hourly.parquet"
    if cache.exists():
        df = pd.read_parquet(cache)
    else:
        df = pd.concat([data_io.load_hospital(raw, h) for h in ("A", "B")], ignore_index=True)
        df.to_parquet(cache, index=False)
    print(f"Loaded {df['patient_id'].nunique():,} patients, {len(df):,} rows "
          f"in {time.time() - t0:.0f}s")

    patients = labels.patient_table(df)
    splits = S.make_splits(patients)
    assert splits["patient_id"].is_unique, "a patient appears in more than one split"
    patients = patients.merge(splits[["patient_id", "split"]], on="patient_id")

    patients.to_csv(out / "patients.csv", index=False)
    splits.to_csv(out / "splits.csv", index=False)
    S.summarize(patients, splits).to_csv(out / "split_summary.csv", index=False)
    audit.variable_availability(df).to_csv(out / "availability.csv", index=False)
    cohort = audit.cohort_summary(df, patients, splits)
    cohort.to_csv(out / "data_audit.csv", index=False)

    print(cohort.pivot(index="metric", columns="hospital", values="value").to_string())


if __name__ == "__main__":
    main()
