"""Step 10 (post hoc): choose a LightGBM + temporal GRU mix on validation only.

Run after 02_train.py and 08_temporal_gru.py, before 03_evaluate.py.

Each model's score is turned into a percentile against its own home
hospital's validation hours, so the two are on the same scale. The mix is

    blend = w * percentile(LightGBM combined) + (1 - w) * percentile(GRU)

with w in {0, 0.25, 0.5, 0.75, 1}. The weight is fixed by one rule, decided
before any blend is scored on test patients: the w with the highest mean
validation share of eligible septic patients reviewed 6-12 h before onset,
averaged over both hospitals, budgets k = 3 and 5, and admission orders 1-5
(home model, validation patients only). Ties go to the larger LightGBM
weight. One weight is used for both hospitals.

Writes data/processed/scores/{A,B}_blend.npy and outputs/blend_selection.json.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import config as C, simulation as S  # noqa: E402

SC = ROOT / "data/processed/scores"
WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)
BUDGETS = (3, 5)


def percentile_fn(ref):
    ref = np.sort(ref)
    return lambda s: (np.searchsorted(ref, s, side="right") / len(ref)).astype(np.float32)


def main():
    rows = pd.read_parquet(ROOT / "data/processed/rows.parquet")
    patients = pd.read_csv(ROOT / "outputs/patients.csv").set_index("patient_id")
    hosp, split = rows["hospital"].to_numpy(), rows["split"].to_numpy()
    blends = {}
    for H in C.HOSPITALS:
        va = (hosp == H) & (split == "val")
        lg = np.load(SC / f"{H}_lgbm_combined.npy")
        gru = np.load(SC / f"{H}_temporal_gru.npy")
        assert len(lg) == len(gru) == len(rows)
        blends[H] = (percentile_fn(lg[va])(lg), percentile_fn(gru[va])(gru))

    results = []
    for H in C.HOSPITALS:
        mask = (hosp == H) & (split == "val")
        r = rows[mask]
        ids = r["patient_id"].drop_duplicates().to_numpy()
        n_hours = r.groupby("patient_id", sort=False).size().loc[ids].to_numpy()
        p = patients.loc[ids]
        pl, pg = blends[H]
        scores = {f"w={w}": (w * pl + (1 - w) * pg)[mask] for w in WEIGHTS}
        cohort = S.Cohort(n_hours=n_hours, t_onset=p["t_onset"].to_numpy(float),
                          group=p["group"].to_numpy(object), offsets=np.r_[0, np.cumsum(n_hours)[:-1]],
                          scores=scores)
        for k in BUDGETS:
            for seed in C.SIM_SEEDS:
                out, _, _ = S.sweep(cohort, list(scores), k=k, seed=seed)
                for name, m in out.items():
                    results.append({"hospital": H, "k": k, "seed": seed, "w": float(name[2:]),
                                    "caught6": m["caught6"], "false_per_shift": m["false_per_shift"]})
    res = pd.DataFrame(results)
    table = res.groupby(["w", "hospital", "k"])["caught6"].mean().unstack(["hospital", "k"])
    table["mean"] = table.mean(axis=1)
    best = float(table["mean"].round(6).iloc[::-1].idxmax())
    print((100 * table).round(1).to_string())
    print("chosen LightGBM weight:", best)

    for H, (pl, pg) in blends.items():
        np.save(SC / f"{H}_blend.npy", (best * pl + (1 - best) * pg).astype(np.float32))
    out = {"rule": __doc__.split("\n\n")[2].strip(),
           "lightgbm_weight": best, "gru_weight": 1 - best,
           "validation_caught6_pct": {f"w={w}": {f"{h}, k={k}": round(100 * table.loc[w, (h, k)], 2)
                                                 for h in C.HOSPITALS for k in BUDGETS}
                                      | {"mean": round(100 * table.loc[w, "mean"], 2)} for w in WEIGHTS}}
    (ROOT / "outputs/blend_selection.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
