"""Step 4: secondary analyses (run after 03_evaluate.py).

1. Before-new-testing check (Tier 1). The testing-signal rule is first
   applied to TRAINING patients only and its firing rate is written to
   outputs/results/testing_signal_training.json before any test patient is
   classified.
2. Failure cases (Tier 0), picked by the frozen rule from the seed-1 A->A run.
3. Null check (acceptance test): LightGBM combined trained on shuffled
   labels must land inside random-k's interval.
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lightgbm as lgb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import config as C, data_io as D, features as F, simulation as S  # noqa: E402
from src.labels import ELIGIBLE  # noqa: E402

RES = ROOT / "outputs/results"
SIGNAL_LABS = ["Lactate", "WBC", "pH", "PaCO2"]


def log(m):
    print(time.strftime("%H:%M:%S"), m, flush=True)


def testing_signal(hourly: pd.DataFrame, patients: pd.DataFrame) -> pd.Series:
    """First hour within 24 h before onset with a new round of testing.

    New lab = measured this hour and not in the previous 12 hours.
    Signal = a new lactate, WBC, pH or PaCO2, or >= 2 new labs in one hour.
    Returns signal hour per eligible septic patient (NaN if none).
    """
    df = hourly.sort_values(["patient_id", "hour"]).reset_index(drop=True)
    grp = df["patient_id"]
    new = {}
    for lab in D.LABS:
        obs = df[lab].notna()
        prev12 = obs.groupby(grp).transform(
            lambda s: s.shift(1).rolling(12, min_periods=1).max()).fillna(0).astype(bool)
        new[lab] = obs & ~prev12
    new = pd.DataFrame(new)
    fire = new[SIGNAL_LABS].any(axis=1) | (new.sum(axis=1) >= 2)
    t_on = df["patient_id"].map(patients.set_index("patient_id")["t_onset"])
    win = (df["hour"] >= t_on - 24) & (df["hour"] < t_on)
    cand = df.loc[fire & win, ["patient_id", "hour"]]
    return cand.groupby("patient_id")["hour"].min()


def main():
    patients = pd.read_csv(ROOT / "outputs/patients.csv")
    hourly = pd.read_parquet(ROOT / "data/processed/hourly.parquet")
    elig = patients[patients["group"] == ELIGIBLE]

    # 1a. freeze the rule on training patients
    tr_ids = elig.loc[elig["split"] == "train", "patient_id"]
    sig_tr = testing_signal(hourly[hourly["patient_id"].isin(tr_ids)], patients)
    freeze = {
        "rule": "first hour within 24 h before onset where lactate, WBC, pH or PaCO2 is new "
                "(unmeasured in the previous 12 h), or >= 2 labs are new in the same hour",
        "training_eligible_patients": int(len(tr_ids)),
        "signal_found_pct": round(100 * sig_tr.reindex(tr_ids).notna().mean(), 1),
        "median_hours_before_onset": float(np.median(
            patients.set_index("patient_id").loc[sig_tr.index, "t_onset"] - sig_tr)),
        "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }
    (RES / "testing_signal_training.json").write_text(json.dumps(freeze, indent=1))
    log(f"testing signal frozen on training: {freeze}")

    # 1b. apply to test patients' first early reviews (seed-1 sweeps, k=3)
    te_ids = elig.loc[elig["split"] == "test", "patient_id"]
    sig = testing_signal(hourly[hourly["patient_id"].isin(te_ids)], patients)
    out = []
    for T in C.HOSPITALS:
        pk = pd.read_pickle(RES / f"review_logs_{T}.pkl")
        ids = test_ids(patients, T)
        pt = patients.set_index("patient_id").loc[ids]
        for pol, logd in pk["logs"].items():
            if logd.empty:
                continue
            pid = ids[logd["cohort_idx"].to_numpy()]
            lead = pt["t_onset"].to_numpy()[logd["cohort_idx"]] - logd["record_hour"].to_numpy()
            early = (pt["group"].to_numpy()[logd["cohort_idx"]] == ELIGIBLE) & (lead > 0) & (lead <= 12)
            first = pd.DataFrame({"pid": pid[early], "h": logd["record_hour"].to_numpy()[early]}) \
                .groupby("pid")["h"].min()
            s = sig.reindex(first.index)
            out.append({"test": T, "policy": pol, "caught": len(first),
                        "ahead_of_new_testing": int((first < s).sum()),
                        "after_new_testing": int((first >= s).sum()),
                        "no_signal_found": int(s.isna().sum())})
    pd.DataFrame(out).to_csv(RES / "before_new_testing.csv", index=False)
    log("before-new-testing done")

    failure_cases(patients)
    null_check()


def test_ids(patients, T):
    rows = pd.read_parquet(ROOT / "data/processed/rows.parquet", columns=["patient_id", "hospital", "split"])
    r = rows[(rows.hospital == T) & (rows.split == "test")]
    return r["patient_id"].drop_duplicates().to_numpy()


def failure_cases(patients):
    """Pick one miss and one false alert by the frozen rule (A->A, seed 1)."""
    pk = pd.read_pickle(RES / "review_logs_A.pkl")
    ids = test_ids(patients, "A")
    pt = patients.set_index("patient_id").loc[ids]
    logd = pk["logs"]["A:lgbm_combined"]
    t_on = pt["t_onset"].to_numpy()
    grp = pt["group"].to_numpy()
    n_h = pt["n_hours"].to_numpy()
    lead = t_on[logd["cohort_idx"]] - logd["record_hour"].to_numpy()
    is_early = (grp[logd["cohort_idx"]] == ELIGIBLE) & (lead > 0) & (lead <= 12)
    caught = set(logd.loc[is_early, "cohort_idx"])
    cls = S.classify(t_on, grp, logd["cohort_idx"].to_numpy(), logd["record_hour"].to_numpy())
    elig_idx = np.flatnonzero(grp == ELIGIBLE)
    missed = [i for i in elig_idx if i not in caught]
    win = {i: int(min(t_on[i], n_h[i]) - max(0, t_on[i] - 12)) for i in missed}
    miss = max(missed, key=lambda i: (win[i], -i))
    false_counts = logd.loc[cls == S.FALSE, "cohort_idx"].value_counts()
    fa = int(false_counts.index[0])
    cases = {
        "missed": {"patient_id": ids[miss], "cohort_idx": int(miss), "t_onset": float(t_on[miss]),
                   "hours_in_window": win[miss], "n_hours": int(n_h[miss])},
        "false_alert": {"patient_id": ids[fa], "cohort_idx": fa,
                        "false_reviews": int(false_counts.iloc[0]), "n_hours": int(n_h[fa])},
    }
    (RES / "failure_cases.json").write_text(json.dumps(cases, indent=1))
    log(f"failure cases: {cases}")


def null_check():
    """Shuffled-label LightGBM must not beat random-k (A->A, k=3)."""
    sel = json.loads((ROOT / "outputs/model_selection.json").read_text())
    rows = pd.read_parquet(ROOT / "data/processed/rows.parquet")
    hourly = pd.read_parquet(ROOT / "data/processed/hourly.parquet").sort_values(
        ["patient_id", "hour"], kind="stable").reset_index(drop=True)
    assert (hourly["patient_id"].to_numpy() == rows["patient_id"].to_numpy()).all()
    variables = json.loads((ROOT / "outputs/variables_used.json").read_text())["used"]
    base = F.causal_base(hourly, variables)
    del hourly
    hosp, split = rows["hospital"].to_numpy(), rows["split"].to_numpy()
    tr = (hosp == "A") & (split == "train") & rows["in_training"].to_numpy()
    va = (hosp == "A") & (split == "val") & rows["in_training"].to_numpy()
    pools = F.fit_pools(base, tr)
    X = F.assemble(base, pools, "combined")
    rng = np.random.default_rng(0)
    y = rows["target"].to_numpy().copy()
    y_tr = rng.permutation(y[tr])
    y_va = rng.permutation(y[va])
    params = sel["A_lgbm_combined"]["selected"]
    spw = (len(y_tr) - y_tr.sum()) / y_tr.sum()
    p = {**C.LGBM_FIXED, **params, "scale_pos_weight": spw, "metric": "binary_logloss"}
    dtr = lgb.Dataset(X[tr], y_tr)
    dva = lgb.Dataset(X[va], y_va, weight=np.where(y_va == 1, spw, 1.0), reference=dtr)
    booster = lgb.train(p, dtr, num_boost_round=C.MAX_ROUNDS, valid_sets=[dva],
                        callbacks=[lgb.early_stopping(C.EARLY_STOP, verbose=False)])
    s = booster.predict(X, num_iteration=booster.best_iteration).astype(np.float32)
    te = (hosp == "A") & (split == "test")
    patients = pd.read_csv(ROOT / "outputs/patients.csv").set_index("patient_id")
    r = rows[te]
    ids = r["patient_id"].drop_duplicates().to_numpy()
    n_hours = r.groupby("patient_id", sort=False).size().loc[ids].to_numpy()
    p_ = patients.loc[ids]
    cohort = S.Cohort(n_hours, p_["t_onset"].to_numpy(float), p_["group"].to_numpy(object),
                      np.r_[0, np.cumsum(n_hours)[:-1]], {"shuffled": s[te]})
    vals = []
    for b in range(C.N_BOOT):
        idx = np.random.default_rng([2026, ord("A"), b]).integers(0, len(ids), len(ids))
        res, _, _ = S.sweep(cohort, ["random", "shuffled"], k=3, seed=100_000 + b, resample=idx)
        vals.append((res["random"]["caught6"], res["shuffled"]["caught6"]))
    vals = np.array(vals)
    lo, hi = np.percentile(vals[:, 0], [2.5, 97.5])
    shuffled_point = float(np.mean(vals[:, 1]))
    out = {"random_caught6_interval": [lo, hi], "shuffled_caught6_mean": shuffled_point,
           "shuffled_inside_random_interval": bool(lo <= shuffled_point <= hi),
           "shuffled_rounds": booster.best_iteration}
    (RES / "null_check.json").write_text(json.dumps(out, indent=1))
    log(f"null check: {out}")


if __name__ == "__main__":
    main()
