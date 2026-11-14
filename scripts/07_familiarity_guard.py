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
from src.familiarity import fit_familiarity_guard, summary

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
        guard = fit_familiarity_guard(
            X.loc[train], X.loc[validation],
            quantile=0.01,
            validation_abstention_rate=0.05,
        )
        score = guard.score(X).astype(np.float32)
        unfamiliar = guard.unfamiliar(X)
        np.save(SCORES / f"{source}_familiarity_score.npy", score)
        np.save(SCORES / f"{source}_unfamiliar.npy", unfamiliar)
        source_report = {
            "threshold": guard.row_threshold,
            "n_features": len(guard.columns),
            "validation": summary(guard, X.loc[validation]),
            "test_hospitals": {},
        }
        for target in C.HOSPITALS:
            test = (hospital == target) & (split == "test")
            source_report["test_hospitals"][target] = summary(guard, X.loc[test])
        report["source_models"][source] = source_report

    (OUT / "familiarity_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
