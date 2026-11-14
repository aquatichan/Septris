"""Step 12 (post hoc): does a 3-seed GRU ensemble improve the Septris mix?

Run after 10_blend.py, once scripts/08_temporal_gru.py has also been run with
--seed 2027 and --seed 2028. Rule (fixed before those seeds were trained,
see docs/preregistration.md): the ensemble GRU is the mean of the three seeds'
home-validation percentiles. The GRU inside the chosen mix is replaced by the
ensemble only if the new mix has a higher mean validation catch share (both
hospitals, k = 3 and 5, admission orders 1-5). Test patients are not used.
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
SEEDS = ("temporal_gru", "temporal_gru_s2027", "temporal_gru_s2028")


def pct(ref, s):
    ref = np.sort(ref)
    return (np.searchsorted(ref, s, side="right") / len(ref)).astype(np.float32)


def combine(kind, pl, pg):
    if kind == "max":
        return np.maximum(pl, pg)
    raise ValueError(f"mix kind {kind} not handled here")


def main():
    sel = json.loads(SEL.read_text())
    rows = pd.read_parquet(ROOT / "data/processed/rows.parquet")
    patients = pd.read_csv(ROOT / "outputs/patients.csv").set_index("patient_id")
    hosp, split = rows["hospital"].to_numpy(), rows["split"].to_numpy()
    mixes, ens = {}, {}
    for H in C.HOSPITALS:
        va = (hosp == H) & (split == "val")
        lg = np.load(SC / f"{H}_lgbm_combined.npy")
        pl = pct(lg[va], lg)
        seeds = [np.load(SC / f"{H}_{name}.npy") for name in SEEDS]
        pens = np.mean([pct(s[va], s) for s in seeds], axis=0)
        ens[H] = pens
        pg = pct(seeds[0][va], seeds[0])
        mixes[H] = {"current": combine(sel["kind"], pl, pg), "with ensemble": combine(sel["kind"], pl, pens)}

    res = []
    for H in C.HOSPITALS:
        mask = (hosp == H) & (split == "val")
        r = rows[mask]
        ids = r["patient_id"].drop_duplicates().to_numpy()
        n_hours = r.groupby("patient_id", sort=False).size().loc[ids].to_numpy()
        p = patients.loc[ids]
        scores = {k: v[mask] for k, v in mixes[H].items()}
        cohort = S.Cohort(n_hours=n_hours, t_onset=p["t_onset"].to_numpy(float),
                          group=p["group"].to_numpy(object), offsets=np.r_[0, np.cumsum(n_hours)[:-1]],
                          scores=scores)
        for k in (3, 5):
            for seed in C.SIM_SEEDS:
                out, _, _ = S.sweep(cohort, list(scores), k=k, seed=seed)
                res += [{"hospital": H, "k": k, "seed": seed, "mix": m, "caught6": v["caught6"]}
                        for m, v in out.items()]
    t = pd.DataFrame(res).groupby(["mix", "hospital", "k"])["caught6"].mean().unstack(["hospital", "k"])
    t["mean"] = t.mean(axis=1)
    print((100 * t).round(2).to_string())
    use = bool(t.loc["with ensemble", "mean"] > t.loc["current", "mean"])
    print("use ensemble:", use)
    for H in C.HOSPITALS:
        np.save(SC / f"{H}_temporal_gru_ens.npy", ens[H])
    sel["gru_ensemble"] = {"seeds": list(SEEDS), "used": use,
                           "validation_caught6_pct": {m: {f"{h}, k={k}": round(100 * t.loc[m, (h, k)], 2)
                                                          for h in C.HOSPITALS for k in (3, 5)}
                                                      | {"mean": round(100 * t.loc[m, "mean"], 2)}
                                                      for m in t.index}}
    if use:
        for H in C.HOSPITALS:
            np.save(SC / f"{H}_blend.npy", mixes[H]["with ensemble"])
    SEL.write_text(json.dumps(sel, indent=1))


if __name__ == "__main__":
    main()
