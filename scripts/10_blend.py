"""Step 10 (post hoc): choose how to combine LightGBM and the temporal GRU,
on validation patients only.

Run after 02_train.py and 08_temporal_gru.py, before 03_evaluate.py.

Each model's score is first turned into a percentile against its own home
hospital's validation hours, so the two are on the same 0-1 scale.
Candidates:

  avg w      w * pct(LightGBM) + (1 - w) * pct(GRU), w in {0, .25, .5, .75, 1}
             (w = 0 is the GRU alone, w = 1 is LightGBM alone)
  max        the larger of the two percentiles (a bed ranks high if EITHER
             model is worried about it)
  alternate  review slots in a shift alternate between the two models'
             top picks (LightGBM first, or GRU first)

Selection rule: the candidate with the highest mean validation share of
eligible septic patients reviewed 6-12 h before onset, averaged over both
hospitals, budgets k = 3 and 5, and admission orders 1-5 (home model,
validation patients only). Ties go to the simpler candidate (earlier in the
list). Test patients are never used.

History (see docs/preregistration.md): the first version of this rule had only
the "avg w" candidates and picked w = 0 (GRU alone). After the test-set
comparison showed the two models catch largely different patients, "max" and
"alternate" were added and the rule was re-run on validation only.

Writes data/processed/scores/{A,B}_blend.npy (one row of scores, or two rows
for an alternating candidate) and outputs/blend_selection.json.
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
BUDGETS = (3, 5)


def percentile_fn(ref):
    ref = np.sort(ref)
    return lambda s: (np.searchsorted(ref, s, side="right") / len(ref)).astype(np.float32)


def candidates(pl, pg):
    out = {f"avg w={w}": w * pl + (1 - w) * pg for w in (0.0, 0.25, 0.5, 0.75, 1.0)}
    out["max"] = np.maximum(pl, pg)
    out["alternate, LightGBM first"] = np.stack([pl, pg])
    out["alternate, GRU first"] = np.stack([pg, pl])
    return out


def describe(name):
    if name.startswith("avg"):
        w = float(name.split("=")[1])
        return {"kind": "average", "lightgbm_weight": w}
    if name == "max":
        return {"kind": "max", "lightgbm_weight": 0.5}
    return {"kind": "alternate", "lightgbm_weight": 0.5, "first": "lightgbm" if "LightGBM first" in name else "gru"}


def main():
    rows = pd.read_parquet(ROOT / "data/processed/rows.parquet")
    patients = pd.read_csv(ROOT / "outputs/patients.csv").set_index("patient_id")
    hosp, split = rows["hospital"].to_numpy(), rows["split"].to_numpy()
    pct = {}
    for H in C.HOSPITALS:
        va = (hosp == H) & (split == "val")
        lg = np.load(SC / f"{H}_lgbm_combined.npy")
        gru = np.load(SC / f"{H}_temporal_gru.npy")
        assert len(lg) == len(gru) == len(rows)
        pct[H] = (percentile_fn(lg[va])(lg), percentile_fn(gru[va])(gru))

    results = []
    for H in C.HOSPITALS:
        mask = (hosp == H) & (split == "val")
        r = rows[mask]
        ids = r["patient_id"].drop_duplicates().to_numpy()
        n_hours = r.groupby("patient_id", sort=False).size().loc[ids].to_numpy()
        p = patients.loc[ids]
        cands = candidates(*pct[H])
        scores = {name: (s[:, mask] if s.ndim == 2 else s[mask]) for name, s in cands.items()}
        cohort = S.Cohort(n_hours=n_hours, t_onset=p["t_onset"].to_numpy(float),
                          group=p["group"].to_numpy(object), offsets=np.r_[0, np.cumsum(n_hours)[:-1]],
                          scores=scores)
        for k in BUDGETS:
            for seed in C.SIM_SEEDS:
                out, _, _ = S.sweep(cohort, list(scores), k=k, seed=seed)
                for name, m in out.items():
                    results.append({"hospital": H, "k": k, "seed": seed, "candidate": name,
                                    "caught6": m["caught6"]})
    res = pd.DataFrame(results)
    order = list(candidates(*pct["A"]).keys())
    table = res.groupby(["candidate", "hospital", "k"])["caught6"].mean().unstack(["hospital", "k"]).loc[order]
    table["mean"] = table.mean(axis=1)
    best = table["mean"].round(6).idxmax()  # first (simplest) wins ties
    print((100 * table).round(1).to_string())
    print("chosen:", best)

    for H, (pl, pg) in pct.items():
        np.save(SC / f"{H}_blend.npy", candidates(pl, pg)[best].astype(np.float32))
    out = {"chosen": best, **describe(best),
           "validation_caught6_pct": {name: {f"{h}, k={k}": round(100 * table.loc[name, (h, k)], 2)
                                             for h in C.HOSPITALS for k in BUDGETS}
                                      | {"mean": round(100 * table.loc[name, "mean"], 2)} for name in order}}
    (ROOT / "outputs/blend_selection.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
