"""Step 07: fit a frozen familiarity guard for each source hospital.

The guard does not change the preregistered sepsis results. It reports whether
the combined feature pattern at a given hour is unlike the source hospital's
training distribution. Thresholds are selected on source validation rows only.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src import config as C, features as F
from src.familiarity import FamiliarityGuard

OUT = ROOT / "outputs"
SCORES = ROOT / "data/processed/scores"


def main():
    rows = pd.read_parquet(ROOT / "data/processed/rows.parquet")
    hourly = pd.read_parquet(ROOT / "data/processed/hourly.parquet").sort_values(
        ["patient_id", "hour"], kind="stable"
    ).reset_index(drop=True)
    variables = json.loads((OUT / "variables_used.json").read_text())["used"]
    base = F.causal_base(hourly, variables)
    hospital = rows["hospital"].to_numpy()
    split = rows["split"].to_numpy()
    report = {"method": {
        "name": "feature-range familiarity guard",
        "description": "Flags feature patterns outside source-hospital validation range; does not alter model scores.",
        "feature_quantile": 0.01,
        "validation_abstention_rate": 0.05,
    }, "source_models": {}}

    for source in C.HOSPITALS:
        train = (hospital == source) & (split == "train") & rows["in_training"].to_numpy()
        validation = (hospital == source) & (split == "val") & rows["in_training"].to_numpy()
        pools = F.fit_pools(base, train)
        X = F.assemble(base, pools, "combined")
        # Same rule as src.familiarity.fit_familiarity_guard, computed one column at a
        # time so the full feature table is never copied (the copy ran out of memory
        # on an 8 GB machine).
        cols = list(X.columns)
        lower, upper = np.empty(len(cols)), np.empty(len(cols))
        outside = np.zeros(len(X), np.float32)
        for j, c in enumerate(cols):
            v = X[c].to_numpy()
            lower[j], upper[j] = np.quantile(v[train], [0.01, 0.99])
            outside += (v < lower[j]) | (v > upper[j])
        score = outside / len(cols)
        threshold = float(np.quantile(score[validation], 1 - 0.05))
        guard = FamiliarityGuard(tuple(cols), lower, upper, threshold, 0.01)
        unfamiliar = score > threshold

        def summary(_guard, mask):
            sc = score[mask]
            return {"median_out_of_range_share": float(np.median(sc)),
                    "unfamiliar_share": float((sc > threshold).mean()), "threshold": threshold,
                    "feature_quantile": 0.01, "n_features": len(cols)}
        np.save(SCORES / f"{source}_familiarity_score.npy", score)
        np.save(SCORES / f"{source}_unfamiliar.npy", unfamiliar)
        source_report = {
            "threshold": guard.row_threshold,
            "n_features": len(guard.columns),
            "validation": summary(guard, validation),
            "test_hospitals": {},
        }
        for target in C.HOSPITALS:
            test = (hospital == target) & (split == "test")
            source_report["test_hospitals"][target] = summary(guard, test)
        report["source_models"][source] = source_report
        del X

    (OUT / "familiarity_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
