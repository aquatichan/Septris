"""Validation-only gate for new temporal-model candidates.

This script prevents a common failure mode: train many variants, inspect test
catches, then publish the largest number. It reads only source-hospital
validation patients when selecting a candidate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src import config as C, simulation as S

SCORES = ROOT / "data" / "processed" / "scores"
OUT = ROOT / "outputs" / "robust_candidate_selection.json"


def validation_cohort(rows: pd.DataFrame, patients: pd.DataFrame, source: str, scores: dict):
    """Build a cohort exclusively from the source's validation patients."""
    mask = ((rows["hospital"] == source) & (rows["split"] == "val")).to_numpy()
    r = rows.loc[mask]
    ids = r["patient_id"].drop_duplicates().to_numpy()
    n_hours = r.groupby("patient_id", sort=False).size().reindex(ids).to_numpy()
    p = patients.loc[ids]
    return S.Cohort(
        n_hours=n_hours,
        t_onset=p["t_onset"].to_numpy(float),
        group=p["group"].to_numpy(object),
        offsets=np.r_[0, np.cumsum(n_hours)[:-1]],
        scores={name: score[mask] for name, score in scores.items()},
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True,
                    help="comma-separated score suffixes, e.g. temporal_gru,gru_early_values")
    ap.add_argument("--output", type=Path, default=OUT)
    args = ap.parse_args()
    candidates = [x.strip() for x in args.candidates.split(",") if x.strip()]
    if len(candidates) < 2:
        ap.error("supply the existing comparator and at least one new candidate")

    rows = pd.read_parquet(ROOT / "data" / "processed" / "rows.parquet")
    patients = pd.read_csv(ROOT / "outputs" / "patients.csv").set_index("patient_id")
    report = {
        "protocol": ("source-hospital validation patients only; no target-hospital or held-out-test "
                     "labels are used for candidate selection"),
        "objective": "mean caught 6-12 h early, 20 beds, 3 reviews per 12-hour shift, five admission orders",
        "candidates": candidates,
        "selected": {},
        "results": {},
    }

    for source in C.HOSPITALS:
        score = {}
        for name in candidates:
            path = SCORES / f"{source}_{name}.npy"
            if not path.exists():
                raise FileNotFoundError(f"missing {path}; train {name!r} for source {source} first")
            score[name] = np.load(path)
            if len(score[name]) != len(rows):
                raise ValueError(f"{path}: score length does not match rows")
        cohort = validation_cohort(rows, patients, source, score)
        result = {}
        for name in candidates:
            runs = [S.sweep(cohort, [name], k=C.PRIMARY_K, seed=seed)[0][name]
                    for seed in C.SIM_SEEDS]
            result[name] = {
                "caught6_pct": round(100 * float(np.mean([r["caught6"] for r in runs])), 3),
                "false_reviews_per_shift": round(float(np.mean([r["false_per_shift"] for r in runs])), 4),
                "eligible_cases": int(runs[0]["eligible"]),
            }
        indexed = {name: i for i, name in enumerate(candidates)}
        chosen = max(candidates, key=lambda name: (
            result[name]["caught6_pct"], -indexed[name], -result[name]["false_reviews_per_shift"]
        ))
        report["results"][source] = result
        report["selected"][source] = chosen
        print(f"{source}: {chosen} ({result[chosen]['caught6_pct']:.3f}% validation caught early)")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
