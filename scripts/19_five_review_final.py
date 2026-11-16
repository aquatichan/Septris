"""Five chart reviews per shift for the final Septris (calibrated LightGBM + GRU blend).

The team reports 5 reviews per 20-bed, 12-hour shift as its main budget (the
pre-registered primary was 3; it is still reported alongside). 03_evaluate.py
only ran the final calibrated blend at k = 3, so this script adds k = 5 for it,
using exactly the same cohorts, admission-order seeds and bootstrap resamples
as 03_evaluate.py. Random, SIRS, LightGBM and GRU are recomputed here too; they
must match outputs/results/results_table.csv (checked at the end).

Output: outputs/results/five_review_final.csv
"""
import importlib.util
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import config as C  # noqa: E402
from src import simulation as S  # noqa: E402

spec = importlib.util.spec_from_file_location("ev", ROOT / "scripts/03_evaluate.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

K = 5
OUT = ROOT / "outputs/results/five_review_final.csv"
METRICS = ["caught6", "false_per_shift", "caught_any", "missed"]


def main():
    rows = pd.read_parquet(ROOT / "data/processed/rows.parquet")
    patients = pd.read_csv(ROOT / "outputs/patients.csv")
    cohorts, _ = ev.build_cohorts(rows, patients)
    pols = ["random", "sirs"] + [f"{H}:{m}" for H in C.HOSPITALS for m in ("lgbm_combined", "temporal_gru", "lgbm_gru_blend")]
    out = []
    for T, c in cohorts.items():
        point = []
        for seed in C.SIM_SEEDS:
            res, _, _ = S.sweep(c["cohort"], pols, k=K, seed=seed)
            point += [{"policy": p, **{m: res[p][m] for m in METRICS + ["eligible"]}} for p in pols]
        point = pd.DataFrame(point).groupby("policy").mean(numeric_only=True)
        boot = []
        n = len(c["ids"])
        for b in range(C.N_BOOT):
            rng = np.random.default_rng([2026, ord(T), b])  # same resamples as 03_evaluate.py
            idx = rng.integers(0, n, n)
            res, _, _ = S.sweep(c["cohort"], pols, k=K, seed=100_000 + b, resample=idx)
            boot += [{"policy": p, **{m: res[p][m] for m in METRICS}} for p in pols]
            if b % 50 == 0:
                print(time.strftime("%H:%M:%S"), T, "bootstrap", b, flush=True)
        boot = pd.DataFrame(boot)
        for p in pols:
            g = boot[boot.policy == p]
            r = {"test": T, "k": K, "policy": p, "eligible": int(point.loc[p, "eligible"])}
            for m in METRICS:
                r[m] = float(point.loc[p, m])
                lo, hi = ev.ci(g[m])
                r[f"{m}_lo"], r[f"{m}_hi"] = lo, hi
            out.append(r)
    out = pd.DataFrame(out)
    out.to_csv(OUT, index=False)
    print(out[["test", "policy", "eligible", "caught6", "caught6_lo", "caught6_hi", "false_per_shift"]].round(4).to_string())
    # consistency check against the main evaluation for the policies it already had at k = 5
    old = pd.read_csv(ROOT / "outputs/results/results_table.csv")
    old = old[(old.k == K) & (old.subgroup == "all")].set_index(["test", "policy"])
    for _, r in out.iterrows():
        if (r.test, r.policy) in old.index:
            d = abs(old.loc[(r.test, r.policy), "caught6"] - r.caught6)
            print(f"check {r.test} {r.policy}: |diff| = {d:.6f}")


if __name__ == "__main__":
    main()
