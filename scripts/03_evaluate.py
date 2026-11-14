"""Step 3: evaluate every policy on the test patients (run after 02_train.py).

Tier 0: hourly AUROC/PR-AUC; k=3 review-slot sweep for random, SIRS, LR and
the three LightGBM models in all four hospital pairs (5 admission orders);
200-replicate patient bootstrap with paired differences; subgroups.
Tier 1: NEWS, shortcut ablation, budgets 1/2/5, official utility score.

Outputs go to outputs/results/.
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

from src import config as C, simulation as S, utility as U  # noqa: E402
from src.labels import ELIGIBLE  # noqa: E402

RES = ROOT / "outputs/results"
SC = ROOT / "data/processed/scores"
MODELS = ["lr", "lgbm_values", "lgbm_missing", "lgbm_combined", "temporal_gru", "blend", "lgbm_shortcuts"]
SHARED = ["sirs", "news"]
METRICS = ["caught6", "caught_any", "caught3", "missed", "median_lead",
           "false_per_shift", "late_per_shift", "precision"]


def log(m):
    print(time.strftime("%H:%M:%S"), m, flush=True)


def age_band(a):
    return pd.cut(a, [-1, 49.999, 64.999, 79.999, 1000], labels=["<50", "50-64", "65-79", "80+"])


def build_cohorts(rows, patients):
    scores = {f"{H}:{m}": np.load(SC / f"{H}_{m}.npy") for H in C.HOSPITALS for m in MODELS}
    scores.update({s: np.load(SC / f"{s}.npy") for s in SHARED})
    pt = patients.set_index("patient_id")
    cohorts = {}
    for T in C.HOSPITALS:
        mask = (rows["hospital"].to_numpy() == T) & (rows["split"].to_numpy() == "test")
        r = rows[mask]
        ids = r["patient_id"].drop_duplicates().to_numpy()
        n_hours = r.groupby("patient_id", sort=False).size().loc[ids].to_numpy()
        offsets = np.r_[0, np.cumsum(n_hours)[:-1]]
        p = pt.loc[ids]
        cohorts[T] = {
            "cohort": S.Cohort(n_hours=n_hours, t_onset=p["t_onset"].to_numpy(float),
                               group=p["group"].to_numpy(object), offsets=offsets,
                               scores={k: (v[:, mask] if v.ndim == 2 else v[mask]) for k, v in scores.items()}),
            "ids": ids, "patients": p, "rows": r, "mask": mask,
        }
    return cohorts, scores


def hourly_metrics(rows, scores):
    out = []
    for T in C.HOSPITALS:
        m = (rows["hospital"].to_numpy() == T) & (rows["split"].to_numpy() == "test") \
            & rows["in_training"].to_numpy()
        y = rows["target"].to_numpy()[m]
        for name, s in scores.items():
            if s.ndim == 2:  # alternating policy: no single hourly score
                continue
            H = name.split(":")[0] if ":" in name else "-"
            out.append({"train": H, "test": T, "model": name.split(":")[-1],
                        "auroc": roc_auc_score(y, s[m]), "pr_auc": average_precision_score(y, s[m]),
                        "prevalence": y.mean(), "rows": int(m.sum())})
    return pd.DataFrame(out)


def policies_for(k):
    if k == C.PRIMARY_K:
        return ["random"] + SHARED + [f"{H}:{m}" for H in C.HOSPITALS for m in MODELS]
    return ["random", "sirs"] + [f"{H}:{m}" for H in C.HOSPITALS for m in ("lgbm_combined", "temporal_gru", "blend")]


def subgroup_masks(p):
    ages = age_band(p["age"].to_numpy())
    masks = {f"age {b}": (ages == b) for b in ["<50", "50-64", "65-79", "80+"]}
    masks["sex 0"] = p["gender"].to_numpy() == 0
    masks["sex 1"] = p["gender"].to_numpy() == 1
    masks["fully observed"] = p["fully_observed"].to_numpy(bool)
    return {k: np.asarray(v, bool) for k, v in masks.items()}


def main():
    RES.mkdir(parents=True, exist_ok=True)
    rows = pd.read_parquet(ROOT / "data/processed/rows.parquet")
    patients = pd.read_csv(ROOT / "outputs/patients.csv")
    cohorts, scores = build_cohorts(rows, patients)
    log("cohorts built")

    hourly = hourly_metrics(rows, scores)
    hourly.to_csv(RES / "hourly_metrics.csv", index=False)
    log("hourly metrics done")
    print(hourly.round(4).to_string(index=False))

    # ---- point estimates: mean over 5 admission orders ----
    point, review_logs = [], {}
    for T, c in cohorts.items():
        masks = subgroup_masks(c["patients"])
        for k in (C.PRIMARY_K,) + C.TIER1_BUDGETS:
            pols = policies_for(k)
            for seed in C.SIM_SEEDS:
                res, logs, info = S.sweep(c["cohort"], pols, k=k, seed=seed,
                                          denom_masks=masks if k == C.PRIMARY_K else None)
                for key, m in res.items():
                    pol, _, sub = key.partition("|")
                    point.append({"test": T, "k": k, "seed": seed, "policy": pol,
                                  "subgroup": sub or "all", **m})
                if k == C.PRIMARY_K and seed == 1:
                    review_logs[T] = (logs, info)
        log(f"[{T}] point sweeps done")
    point = pd.DataFrame(point)
    point.to_csv(RES / "sweep_by_seed.csv", index=False)
    pmean = point.groupby(["test", "k", "policy", "subgroup"]).mean(numeric_only=True).reset_index()
    pmean.to_csv(RES / "sweep_point.csv", index=False)

    # save the seed-1 primary review logs for failure analysis and the app
    for T, (logs, info) in review_logs.items():
        pd.to_pickle({"logs": logs, "info": info}, RES / f"review_logs_{T}.pkl")

    # ---- bootstrap: resample patients, new admission order, all policies ----
    boot = []
    for T, c in cohorts.items():
        n = len(c["ids"])
        masks = subgroup_masks(c["patients"])
        for b in range(C.N_BOOT):
            rng = np.random.default_rng([2026, ord(T), b])
            idx = rng.integers(0, n, n)
            for k in (C.PRIMARY_K,) + C.TIER1_BUDGETS:
                res, _, _ = S.sweep(c["cohort"], policies_for(k), k=k, seed=100_000 + b,
                                    resample=idx, denom_masks=masks if k == C.PRIMARY_K else None)
                for key, m in res.items():
                    pol, _, sub = key.partition("|")
                    boot.append({"test": T, "k": k, "rep": b, "policy": pol,
                                 "subgroup": sub or "all", **m})
            if b % 25 == 0:
                log(f"[{T}] bootstrap {b}/{C.N_BOOT}")
    boot = pd.DataFrame(boot)
    boot.to_parquet(RES / "bootstrap.parquet", index=False)
    log("bootstrap done")

    summarize(pmean, boot)
    utility_scores(rows, scores)
    log("all done")


def ci(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return (np.nan, np.nan)
    return tuple(np.percentile(x, [2.5, 97.5]))


def summarize(pmean, boot):
    """Main table with intervals, and paired differences."""
    rows = []
    for (T, k, pol, sub), g in boot.groupby(["test", "k", "policy", "subgroup"]):
        pm = pmean[(pmean.test == T) & (pmean.k == k) & (pmean.policy == pol) & (pmean.subgroup == sub)]
        r = {"test": T, "k": k, "policy": pol, "subgroup": sub,
             "eligible": int(pm["eligible"].iloc[0]) if len(pm) else np.nan}
        for m in METRICS + ["caught6_n", "missed_n"]:
            r[m] = float(pm[m].iloc[0]) if len(pm) else np.nan
            if m in METRICS:
                lo, hi = ci(g[m])
                r[f"{m}_lo"], r[f"{m}_hi"] = lo, hi
        rows.append(r)
    table = pd.DataFrame(rows)
    table.to_csv(RES / "results_table.csv", index=False)

    # paired differences inside each replicate
    piv = boot[boot.subgroup == "all"].pivot_table(index=["test", "k", "rep"], columns="policy",
                                                   values="caught6")
    piv_f = boot[boot.subgroup == "all"].pivot_table(index=["test", "k", "rep"], columns="policy",
                                                     values="false_per_shift")
    pm = pmean[pmean.subgroup == "all"].pivot_table(index=["test", "k"], columns="policy",
                                                    values="caught6")
    diffs = []

    def add(T, k, label, a, b, metric="caught6", src=piv, psrc=pm):
        if a not in src.columns or b not in src.columns:
            return
        d = (src.loc[(T, k)][a] - src.loc[(T, k)][b]).to_numpy()
        point = float(psrc.loc[(T, k)][a] - psrc.loc[(T, k)][b]) if psrc is not None else np.nan
        lo, hi = ci(d)
        diffs.append({"test": T, "k": k, "comparison": label, "metric": metric,
                      "a": a, "b": b, "point": point, "lo": lo, "hi": hi,
                      "excludes_zero": bool(lo > 0 or hi < 0)})

    for T in C.HOSPITALS:
        other = [h for h in C.HOSPITALS if h != T][0]
        for k in (C.PRIMARY_K,) + C.TIER1_BUDGETS:
            for m in (MODELS if k == C.PRIMARY_K else ["lgbm_combined", "temporal_gru", "blend"]):
                home = f"{T}:{m}"
                add(T, k, f"{m} (home) minus random", home, "random")
                add(T, k, f"{m} (external, trained {other}) minus random", f"{other}:{m}", "random")
                add(T, k, f"{m}: home minus external", home, f"{other}:{m}")
                add(T, k, f"{m} (home) minus SIRS", home, "sirs")
            for side, H in (("home", T), ("external", other)):
                add(T, k, f"temporal GRU minus combined ({side})", f"{H}:temporal_gru", f"{H}:lgbm_combined")
                add(T, k, f"blend minus combined ({side})", f"{H}:blend", f"{H}:lgbm_combined")
                add(T, k, f"blend minus temporal GRU ({side})", f"{H}:blend", f"{H}:temporal_gru")
            if k == C.PRIMARY_K:
                add(T, k, "SIRS minus random", "sirs", "random")
                add(T, k, "NEWS minus random", "news", "random")
                add(T, k, "reliance: combined minus values-only (home)",
                    f"{T}:lgbm_combined", f"{T}:lgbm_values")
                add(T, k, "missingness-only (home) minus random", f"{T}:lgbm_missing", "random")
                add(T, k, "combined minus LR (home)", f"{T}:lgbm_combined", f"{T}:lr")
                add(T, k, "shortcuts minus combined (home)", f"{T}:lgbm_shortcuts", f"{T}:lgbm_combined")
                pmf = pmean[pmean.subgroup == "all"].pivot_table(index=["test", "k"], columns="policy",
                                                                 values="false_per_shift")
                add(T, k, "false reviews/shift: combined (home) minus random",
                    f"{T}:lgbm_combined", "random", "false_per_shift", piv_f, pmf)
    pd.DataFrame(diffs).to_csv(RES / "paired_differences.csv", index=False)


def utility_scores(rows, scores):
    """Official utility on test patients; threshold chosen on home validation."""
    hour = rows["hour"].to_numpy()
    hto = rows["hours_to_onset"].to_numpy(float)
    t_onset = rows["t_onset"].to_numpy(float)
    # official labels: 1 from 6 h before onset; t_sepsis = first label hour + 6
    label_first = t_onset - C.LABEL_LEAD_HOURS
    t_sep = U.t_sepsis_rows(label_first)
    hosp, split = rows["hospital"].to_numpy(), rows["split"].to_numpy()
    out = []
    names = [f"{H}:{m}" for H in C.HOSPITALS for m in MODELS] + SHARED
    for name in names:
        s = scores[name]
        if s.ndim == 2:
            continue
        H = name.split(":")[0] if ":" in name else None
        homes = [H] if H else list(C.HOSPITALS)
        for home in homes:
            va = (hosp == home) & (split == "val")
            qs = np.unique(np.quantile(s[va], np.linspace(0.5, 0.995, 60)))
            best = max(qs, key=lambda q: U.normalized_utility(hour[va], t_sep[va], None, s[va] > q))
            for T in C.HOSPITALS:
                te = (hosp == T) & (split == "test")
                out.append({"train": home, "test": T, "model": name.split(":")[-1],
                            "threshold": float(best),
                            "val_utility": U.normalized_utility(hour[va], t_sep[va], None, s[va] > best),
                            "test_utility": U.normalized_utility(hour[te], t_sep[te], None, s[te] > best)})
    pd.DataFrame(out).to_csv(RES / "utility_scores.csv", index=False)


if __name__ == "__main__":
    main()
