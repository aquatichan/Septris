"""Step 11 (post hoc): where LightGBM, the temporal GRU and the mix each win.

Run after 03_evaluate.py. Uses the same test cohorts, bed schedules and
admission orders (seeds 1-5) as the main results. Writes
outputs/results/model_comparison.json:

  overlap    eligible septic patients caught 6-12 h early by LightGBM only,
             GRU only or both (mean over admission orders)
  by_onset   caught share split by how long the patient had been in the ICU
             when sepsis was recorded (<24 h, 24-72 h, >72 h)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import config as C, simulation as S  # noqa: E402
from src.labels import ELIGIBLE  # noqa: E402

SC = ROOT / "data/processed/scores"
RES = ROOT / "outputs/results"
MODELS = ("lgbm_combined", "temporal_gru", "blend")
BUCKETS = (("under 24 h", 0, 24), ("24-72 h", 24, 72), ("over 72 h", 72, 10_000))


def main():
    rows = pd.read_parquet(ROOT / "data/processed/rows.parquet")
    patients = pd.read_csv(ROOT / "outputs/patients.csv").set_index("patient_id")
    hosp, split = rows["hospital"].to_numpy(), rows["split"].to_numpy()
    out = {"overlap": [], "by_onset": []}
    for T in C.HOSPITALS:
        mask = (hosp == T) & (split == "test")
        r = rows[mask]
        ids = r["patient_id"].drop_duplicates().to_numpy()
        n_hours = r.groupby("patient_id", sort=False).size().loc[ids].to_numpy()
        p = patients.loc[ids]
        t_onset, group = p["t_onset"].to_numpy(float), p["group"].to_numpy(object)
        for H in C.HOSPITALS:
            pols = {m: f"{H}:{m}" for m in MODELS}
            scores = {f"{H}:{m}": np.load(SC / f"{H}_{m}.npy")[mask] for m in MODELS}
            cohort = S.Cohort(n_hours=n_hours, t_onset=t_onset, group=group,
                              offsets=np.r_[0, np.cumsum(n_hours)[:-1]], scores=scores)
            for k in (3, 5):
                tallies = []
                for seed in C.SIM_SEEDS:
                    _, logs, info = S.sweep(cohort, list(scores), k=k, seed=seed)
                    elig = np.flatnonzero(group == ELIGIBLE)
                    caught = {}
                    for m, pol in pols.items():
                        lg = logs[pol]
                        cls = S.classify(t_onset, group, lg["cohort_idx"].to_numpy(), lg["record_hour"].to_numpy())
                        caught[m] = set(lg["cohort_idx"].to_numpy()[cls == S.EARLY6])
                    a, g = caught["lgbm_combined"], caught["temporal_gru"]
                    tallies.append({"LightGBM only": len(a - g), "GRU only": len(g - a), "both": len(a & g),
                                    "neither": len(set(elig) - a - g), "mix": len(caught["blend"])})
                    for name, lo, hi in BUCKETS:
                        sel = elig[(t_onset[elig] >= lo) & (t_onset[elig] < hi)]
                        for m in MODELS:
                            out["by_onset"].append({"test": T, "trained": H, "k": k, "seed": seed,
                                                    "onset_after": name, "model": m, "n": len(sel),
                                                    "caught": len(caught[m] & set(sel))})
                mean = pd.DataFrame(tallies).mean().round(1).to_dict()
                out["overlap"].append({"test": T, "trained": H, "k": k, **mean})
    bo = pd.DataFrame(out["by_onset"]).groupby(["test", "trained", "k", "onset_after", "model"]).mean(
        numeric_only=True).reset_index()
    bo["pct"] = (100 * bo["caught"] / bo["n"]).round(1)
    out["by_onset"] = bo.drop(columns="seed").to_dict("records")
    (RES / "model_comparison.json").write_text(json.dumps(out, indent=1))
    print(pd.DataFrame(out["overlap"]).to_string(index=False))
    print(bo.pivot_table(index=["test", "trained", "k", "onset_after"], columns="model", values="pct").to_string())


if __name__ == "__main__":
    main()
