"""Step 15 (post hoc): final choice of how Septris combines its models,
on validation patients only.

Run after 02_train.py (which now also trains Miheer's queue-tuned LightGBM),
08_temporal_gru.py for seeds 2026/2027/2028, 12_gru_ensemble.py and
14_validated_ensemble.py; before 03_evaluate.py.

Components, each turned into a percentile of its home hospital's validation
hours: LightGBM combined (L), queue-tuned LightGBM (Q), 3-seed GRU ensemble
(G). Candidates:

  max(L, G)        the mix chosen earlier (kept unless something beats it)
  max(Q, G)        same rule with the queue-tuned LightGBM
  max(L, Q, G)     highest of all three
  mean(L, G), mean(Q, G), mean(L, Q, G)
  platt blend      Miheer's Platt-calibrated convex blend (14_validated_ensemble.py)
  L, Q, G alone

Rule (same as 10_blend.py): highest mean validation share of eligible septic
patients reviewed 6-12 h before onset over both hospitals, k = 3 and 5,
admission orders 1-5. Ties keep the earlier candidate. Q's hyperparameters
and the platt blend's weight were themselves tuned on this validation queue
metric (at k = 3), so their validation numbers are slightly optimistic. Test
patients are never used here.
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
SEL = ROOT / "outputs/blend_selection.json"


def pct(ref, s):
    ref = np.sort(ref)
    return (np.searchsorted(ref, s, side="right") / len(ref)).astype(np.float32)


def main():
    rows = pd.read_parquet(ROOT / "data/processed/rows.parquet")
    patients = pd.read_csv(ROOT / "outputs/patients.csv").set_index("patient_id")
    hosp, split = rows["hospital"].to_numpy(), rows["split"].to_numpy()
    cands = {}
    for H in C.HOSPITALS:
        va = (hosp == H) & (split == "val")
        ld = lambda n: np.load(SC / f"{H}_{n}.npy")  # noqa: E731
        Lp = pct(ld("lgbm_combined")[va], ld("lgbm_combined"))
        Qp = pct(ld("lgbm_queue_tuned")[va], ld("lgbm_queue_tuned"))
        Gp = ld("temporal_gru_ens")
        cands[H] = {
            "max(L, G)": np.maximum(Lp, Gp), "max(Q, G)": np.maximum(Qp, Gp),
            "max(L, Q, G)": np.maximum(np.maximum(Lp, Qp), Gp),
            "mean(L, G)": (Lp + Gp) / 2, "mean(Q, G)": (Qp + Gp) / 2, "mean(L, Q, G)": (Lp + Qp + Gp) / 3,
            "platt blend": ld("lgbm_gru_blend"), "L alone": Lp, "Q alone": Qp, "G alone": Gp,
        }
    res = []
    for H in C.HOSPITALS:
        mask = (hosp == H) & (split == "val")
        r = rows[mask]
        ids = r["patient_id"].drop_duplicates().to_numpy()
        n_hours = r.groupby("patient_id", sort=False).size().loc[ids].to_numpy()
        p = patients.loc[ids]
        scores = {k: v[mask] for k, v in cands[H].items()}
        cohort = S.Cohort(n_hours=n_hours, t_onset=p["t_onset"].to_numpy(float),
                          group=p["group"].to_numpy(object), offsets=np.r_[0, np.cumsum(n_hours)[:-1]],
                          scores=scores)
        for k in (3, 5):
            for seed in C.SIM_SEEDS:
                out, _, _ = S.sweep(cohort, list(scores), k=k, seed=seed)
                res += [{"hospital": H, "k": k, "c": c, "caught6": v["caught6"]} for c, v in out.items()]
    order = list(cands["A"])
    t = pd.DataFrame(res).groupby(["c", "hospital", "k"])["caught6"].mean().unstack(["hospital", "k"]).loc[order]
    t["mean"] = t.mean(axis=1)
    best = t["mean"].round(6).idxmax()
    print((100 * t).round(2).to_string())
    print("chosen:", best)
    for H in C.HOSPITALS:
        np.save(SC / f"{H}_blend.npy", cands[H][best].astype(np.float32))
    sel = json.loads(SEL.read_text())
    sel["final"] = {"chosen": best,
                    "validation_caught6_pct": {c: {f"{h}, k={k}": round(100 * t.loc[c, (h, k)], 2)
                                                   for h in C.HOSPITALS for k in (3, 5)}
                                               | {"mean": round(100 * t.loc[c, "mean"], 2)} for c in order}}
    SEL.write_text(json.dumps(sel, indent=1))


if __name__ == "__main__":
    main()
