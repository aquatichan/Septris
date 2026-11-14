"""First block: download, parse, onset times, split registry, data audit.

Usage (from the repo root):
    python scripts/setup_data.py                  # download + build
    python scripts/setup_data.py --no-download    # rebuild from files already in data/raw

Writes to outputs/:
    patients.csv       one row per patient (sepsis, t_sepsis, censoring)
    splits.csv         fixed 70/15/15 patient split per hospital (seed 42)
    split_summary.csv  patients and sepsis rate per hospital and split
    availability.csv   how often each variable is recorded at each hospital
    data_audit.csv     cohort summary per hospital (brief section 4)
and caches each hospital as data/processed/hospital_<X>.parquet for fast reloads.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src import audit, data_io, labels, splits as S  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/raw")
    ap.add_argument("--processed-dir", default="data/processed")
    ap.add_argument("--out-dir", default="outputs")
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    data_dir, out_dir = Path(args.data_dir), Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.no_download:
        print("Downloading PhysioNet 2019 training sets A and B...")
        data_io.download(data_dir)

    hospitals = []
    for h in ("A", "B"):
        df = data_io.load_hospital(data_dir, h)
        data_io.save_parquet(df, Path(args.processed_dir) / f"hospital_{h}.parquet")
        print(f"Hospital {h}: {df['patient_id'].nunique():,} patients, {len(df):,} patient-hours")
        hospitals.append(df)
    df = pd.concat(hospitals, ignore_index=True)

    patients = labels.patient_table(df)
    splits = S.make_splits(patients, seed=args.seed)
    assert splits["patient_id"].is_unique, "a patient appears in more than one split"
    summary = S.summarize(patients, splits)
    avail = audit.variable_availability(df)
    cohort = audit.cohort_summary(df, patients, splits)

    patients.to_csv(out_dir / "patients.csv", index=False)
    splits.to_csv(out_dir / "splits.csv", index=False)
    summary.to_csv(out_dir / "split_summary.csv", index=False)
    avail.to_csv(out_dir / "availability.csv", index=False)
    cohort.to_csv(out_dir / "data_audit.csv", index=False)

    print("\nSplits:")
    print(summary.to_string(index=False))
    sep = patients[patients["sepsis"] == 1]
    print(f"\nSepsis patients: {len(sep):,} "
          f"({sep['onset_censored'].sum():,} with onset in the first 6 ICU hours, "
          "excluded from lead-time metrics)")
    for col, name in (("flag_hours_rule", "brief's <1%-of-hours rule"),
                      ("flag_hospital_specific", "hospital-specific rule")):
        flagged = avail.loc[avail[col], "variable"].tolist()
        print(f"\nFlagged by the {name}: {flagged or 'none'}")
    print(f"\nWrote outputs to {out_dir}/")


if __name__ == "__main__":
    main()
