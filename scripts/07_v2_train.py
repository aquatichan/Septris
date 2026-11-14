"""Version 2 (post hoc): train on v1 combined + v2 features, decide on VALIDATION only.

Built after version 1's test results were seen, so nothing here looks at
test patients. Outputs:
  data/processed/scores/<H>_lgbm_v2.npy       version 2 scores, every row
  data/processed/scores/<H>to<T>_lgbm_v2_ft.npy  fine-tuned on a slice of T's
                                                   training patients (adaptation)
  outputs/v2/validation_comparison.csv          v1 vs v2 vs fine-tuned, validation sweep
  outputs/v2/model_selection.json
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
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

from src import config as C, features as F, features_v2 as F2, simulation as S  # noqa: E402

SC = ROOT / "data/processed/scores"
OUT = ROOT / "outputs/v2"
FT_PATIENTS = 1000      # adaptation slice of the new hospital's TRAINING patients
FT_ROUNDS = 300


def log(m):
    print(time.strftime("%H:%M:%S"), m, flush=True)


def fit(Xtr, ytr, Xva, yva, params, init=None):
    spw = (len(ytr) - ytr.sum()) / max(1, ytr.sum())
    p = {**C.LGBM_FIXED, **params, "scale_pos_weight": spw, "metric": "binary_logloss"}
    dtr = lgb.Dataset(Xtr, ytr)
    dva = lgb.Dataset(Xva, yva, weight=np.where(yva == 1, spw, 1.0), reference=dtr)
    rounds = FT_ROUNDS if init is not None else C.MAX_ROUNDS
    b = lgb.train(p, dtr, num_boost_round=rounds, valid_sets=[dva], init_model=init,
                  callbacks=[lgb.early_stopping(C.EARLY_STOP, verbose=False)])
    pv = b.predict(Xva, num_iteration=b.best_iteration)
    return b, average_precision_score(yva, pv), roc_auc_score(yva, pv)


def _slice(d, a, b, n):
    out = {}
    for k, v in d.items():
        if isinstance(v, np.ndarray) and len(v) == n:
            out[k] = v[a:b]
        elif isinstance(v, dict):
            out[k] = {kk: (vv[a:b] if isinstance(vv, np.ndarray) and len(vv) == n else vv) for kk, vv in v.items()}
        else:
            out[k] = v
    out["n"] = b - a
    return out


def chunks(n, size=250_000):
    return [(a, min(n, a + size)) for a in range(0, n, size)]


def features(base, xb, pools, pools2, a, b):
    """Version 2 feature table for rows a:b (features are row-wise, so chunks are exact)."""
    n = base["n"]
    bs, xs = _slice(base, a, b, n), _slice(xb, a, b, n)
    vals = F.values_block(bs, pools)
    return pd.concat([vals, F.missing_block(bs), F2.extra_block(bs, xs, pools2, vals)], axis=1)


def build(base, xb, pools, pools2, mask):
    """Feature rows where mask is True, built chunk by chunk."""
    parts = [features(base, xb, pools, pools2, a, b)[mask[a:b]] for a, b in chunks(base["n"]) if mask[a:b].any()]
    return pd.concat(parts, ignore_index=True)


def predict_all(booster, base, xb, pools, pools2, it=None):
    return np.concatenate([booster.predict(features(base, xb, pools, pools2, a, b), num_iteration=it)
                           for a, b in chunks(base["n"])]).astype(np.float32)


def val_cohort(rows, patients, T, scores):
    m = (rows["hospital"].to_numpy() == T) & (rows["split"].to_numpy() == "val")
    r = rows[m]
    ids = r["patient_id"].drop_duplicates().to_numpy()
    nh = r.groupby("patient_id", sort=False).size().loc[ids].to_numpy()
    p = patients.loc[ids]
    return S.Cohort(nh, p["t_onset"].to_numpy(float), p["group"].to_numpy(object),
                    np.r_[0, np.cumsum(nh)[:-1]], {k: v[m] for k, v in scores.items()})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = pd.read_parquet(ROOT / "data/processed/rows.parquet")
    patients = pd.read_csv(ROOT / "outputs/patients.csv").set_index("patient_id")
    hourly = pd.read_parquet(ROOT / "data/processed/hourly.parquet").sort_values(
        ["patient_id", "hour"], kind="stable").reset_index(drop=True)
    assert (hourly["patient_id"].to_numpy() == rows["patient_id"].to_numpy()).all()
    variables = json.loads((ROOT / "outputs/variables_used.json").read_text())["used"]
    base = F.causal_base(hourly, variables)
    del hourly
    xb = F2.extra_base(base)
    log("bases built")
    hosp, split = rows["hospital"].to_numpy(), rows["split"].to_numpy()
    in_tr, y, pid = rows["in_training"].to_numpy(), rows["target"].to_numpy(), rows["patient_id"].to_numpy()
    sel = {}
    boosters = {}

    for H in C.HOSPITALS:
        tr = (hosp == H) & (split == "train") & in_tr
        va = (hosp == H) & (split == "val") & in_tr
        pools, pools2 = F.fit_pools(base, tr), F2.fit_pools_v2(xb, tr)
        Xtr, Xva = build(base, xb, pools, pools2, tr), build(base, xb, pools, pools2, va)
        log(f"[{H}] v2 features train {Xtr.shape} val {Xva.shape}")
        best = None
        trials = []
        for params in C.LGBM_SEARCH:
            b, pr, auc = fit(Xtr, y[tr], Xva, y[va], params)
            trials.append({**params, "val_pr_auc": pr, "val_auroc": auc, "rounds": b.best_iteration})
            log(f"[{H}] v2 {params} PR-AUC {pr:.4f} AUROC {auc:.4f} rounds {b.best_iteration}")
            if best is None or pr > best[1]:
                best = (b, pr, params)
        b, pr, params = best
        cols = list(Xtr.columns)
        del Xtr, Xva
        np.save(SC / f"{H}_lgbm_v2.npy", predict_all(b, base, xb, pools, pools2, b.best_iteration))
        b.save_model(str(ROOT / f"outputs/models/{H}_lgbm_v2.txt"), num_iteration=b.best_iteration)
        sel[f"{H}_lgbm_v2"] = {"selected": params, "val_pr_auc": pr, "trials": trials, "features": cols}
        boosters[H] = (b, params)

        # adaptation: continue training on a slice of the OTHER hospital's training patients,
        # using that hospital's own pools (it would have its own data), early-stopped on its validation
        T = "B" if H == "A" else "A"
        t_tr_ids = np.unique(pid[(hosp == T) & (split == "train")])
        slice_ids = np.random.default_rng(2026).choice(t_tr_ids, FT_PATIENTS, replace=False)
        ft_tr = np.isin(pid, slice_ids) & in_tr
        ft_va = (hosp == T) & (split == "val") & in_tr
        pools_t, pools2_t = F.fit_pools(base, ft_tr), F2.fit_pools_v2(xb, ft_tr)
        Xft, Xfv = build(base, xb, pools_t, pools2_t, ft_tr), build(base, xb, pools_t, pools2_t, ft_va)
        bft, prft, aucft = fit(Xft, y[ft_tr], Xfv, y[ft_va], params, init=b)
        del Xft, Xfv
        np.save(SC / f"{H}to{T}_lgbm_v2_ft.npy", predict_all(bft, base, xb, pools_t, pools2_t, bft.best_iteration))
        sel[f"{H}to{T}_lgbm_v2_ft"] = {"base": f"{H}_lgbm_v2", "slice_patients": FT_PATIENTS,
                                        "val_pr_auc_target": prft, "val_auroc_target": aucft,
                                        "extra_rounds": bft.best_iteration - b.best_iteration}
        log(f"[{H}->{T}] fine-tuned on {FT_PATIENTS} {T} patients: {T} val PR-AUC {prft:.4f} AUROC {aucft:.4f}")
        (OUT / "model_selection.json").write_text(json.dumps(sel, indent=1))

    # validation-only decision: review-slot sweep on validation patients
    names = [f"{H}_lgbm_combined" for H in C.HOSPITALS] + [f"{H}_lgbm_v2" for H in C.HOSPITALS] \
        + ["AtoB_lgbm_v2_ft", "BtoA_lgbm_v2_ft"]
    scores = {n: np.load(SC / f"{n}.npy") for n in names}
    res = []
    for T in C.HOSPITALS:
        coh = val_cohort(rows, patients, T, scores)
        for k in (3,):
            runs = [S.sweep(coh, ["random"] + names, k=k, seed=s)[0] for s in C.SIM_SEEDS]
            for n in ["random"] + names:
                res.append({"val_hospital": T, "k": k, "policy": n,
                            "caught6": np.mean([r[n]["caught6"] for r in runs]),
                            "false_per_shift": np.mean([r[n]["false_per_shift"] for r in runs])})
        m = (hosp == T) & (split == "val") & in_tr
        for n in names:
            res.append({"val_hospital": T, "k": "hourly", "policy": n,
                        "caught6": roc_auc_score(y[m], scores[n][m]),
                        "false_per_shift": average_precision_score(y[m], scores[n][m])})
    pd.DataFrame(res).to_csv(OUT / "validation_comparison.csv", index=False)
    log("validation comparison written (k='hourly' rows hold AUROC / PR-AUC)")


if __name__ == "__main__":
    main()
