"""Step 2: build features and train every model on each home hospital.

For each home hospital (A, B):
  - logistic regression on current values
  - LightGBM on values-only, missingness-only, combined (6-config search,
    selection by home validation PR-AUC)
  - Tier 1: LightGBM combined + shortcut fields, using the combined model's
    selected configuration
Every model scores every hour of both hospitals; scores are saved to
data/processed/scores/<train>_<model>.npy aligned with hourly.parquet.

    python scripts/02_train.py            # resumes: skips finished models
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
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from src import config as C, data_io as D, features as F, labels as L  # noqa: E402

OUT = ROOT / "outputs"
SCORES = ROOT / "data/processed/scores"
MODELS = ROOT / "outputs/models"


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def load():
    df = pd.read_parquet(ROOT / "data/processed/hourly.parquet")
    df = df.sort_values(["patient_id", "hour"], kind="stable").reset_index(drop=True)
    patients = pd.read_csv(OUT / "patients.csv")
    df = L.add_target(df, patients)
    split = patients.set_index("patient_id")["split"]
    df["split"] = df["patient_id"].map(split)
    av = pd.read_csv(OUT / "availability.csv")
    drop = set(av.loc[av["flag_hospital_specific"], "variable"])
    variables = [v for v in D.MEASURED if v not in drop]
    return df, variables, sorted(drop)


def fit_lgbm(Xtr, ytr, Xva, yva, params):
    spw = (len(ytr) - ytr.sum()) / max(1, ytr.sum())
    p = {**C.LGBM_FIXED, **params, "scale_pos_weight": spw, "metric": "binary_logloss"}
    # validation carries the same class weight as training, so the early-
    # stopping log-loss measures the same objective (see deviations log)
    dtr = lgb.Dataset(Xtr, ytr, free_raw_data=False)
    dva = lgb.Dataset(Xva, yva, weight=np.where(yva == 1, spw, 1.0), reference=dtr)
    booster = lgb.train(p, dtr, num_boost_round=C.MAX_ROUNDS, valid_sets=[dva],
                        callbacks=[lgb.early_stopping(C.EARLY_STOP, verbose=False)])
    pv = booster.predict(Xva, num_iteration=booster.best_iteration)
    return booster, average_precision_score(yva, pv), roc_auc_score(yva, pv)


def main():
    SCORES.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    log("loading")
    df, variables, dropped = load()
    log(f"{len(df):,} rows; variables {len(variables)}; dropped {dropped}")
    base = F.causal_base(df, variables)
    df = df[["patient_id", "hospital", "hour", "split", "target", "in_training",
             "t_onset", "group", "hours_to_onset"]].copy()  # free raw columns
    log("causal base built")
    hosp, split = df["hospital"].to_numpy(), df["split"].to_numpy()
    in_tr, y = df["in_training"].to_numpy(), df["target"].to_numpy()
    np.save(SCORES / "sirs.npy", F.sirs_count(base).astype(np.float32))
    np.save(SCORES / "news.npy", F.news_score(base).astype(np.float32))
    X_missing = F.missing_block(base)
    summary_path = OUT / "model_selection.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}

    for H in C.HOSPITALS:
        tr = (hosp == H) & (split == "train") & in_tr
        va = (hosp == H) & (split == "val") & in_tr
        pools = F.fit_pools(base, tr)
        X_values = F.values_block(base, pools)
        sets = {
            "values": X_values,
            "missing": X_missing,
            "combined": pd.concat([X_values, X_missing], axis=1),
        }
        log(f"[{H}] features ready: train rows {tr.sum():,} (pos {y[tr].sum():,}), val {va.sum():,}")

        # logistic regression on current values
        f_lr = SCORES / f"{H}_lr.npy"
        if not f_lr.exists():
            cur = F.current_values(base, pools).to_numpy(np.float64)
            sc = StandardScaler().fit(cur[tr])
            lr = LogisticRegression(class_weight="balanced", max_iter=1000)
            lr.fit(sc.transform(cur[tr]), y[tr])
            s = lr.predict_proba(sc.transform(cur))[:, 1].astype(np.float32)
            np.save(f_lr, s)
            summary[f"{H}_lr"] = {"val_pr_auc": average_precision_score(y[va], s[va]),
                                  "val_auroc": roc_auc_score(y[va], s[va])}
            summary_path.write_text(json.dumps(summary, indent=1))
            log(f"[{H}] LR val PR-AUC {summary[f'{H}_lr']['val_pr_auc']:.4f}")
            del cur

        for name, X in sets.items():
            f = SCORES / f"{H}_lgbm_{name}.npy"
            if f.exists():
                continue
            Xtr, Xva = X[tr], X[va]
            best = None
            trials = []
            for params in C.LGBM_SEARCH:
                t0 = time.time()
                booster, pr, auc = fit_lgbm(Xtr, y[tr], Xva, y[va], params)
                trials.append({**params, "val_pr_auc": pr, "val_auroc": auc,
                               "rounds": booster.best_iteration, "secs": round(time.time() - t0)})
                log(f"[{H}] {name} {params} PR-AUC {pr:.4f} AUROC {auc:.4f} "
                    f"rounds {booster.best_iteration} {time.time() - t0:.0f}s")
                if best is None or pr > best[1]:
                    best = (booster, pr, params)
            booster, pr, params = best
            booster.save_model(str(MODELS / f"{H}_lgbm_{name}.txt"),
                               num_iteration=booster.best_iteration)
            s = booster.predict(X, num_iteration=booster.best_iteration).astype(np.float32)
            np.save(f, s)
            summary[f"{H}_lgbm_{name}"] = {"selected": params, "val_pr_auc": pr, "trials": trials,
                                           "features": list(X.columns)}
            summary_path.write_text(json.dumps(summary, indent=1))

        # Tier 1: shortcut ablation, same configuration as combined
        f = SCORES / f"{H}_lgbm_shortcuts.npy"
        if not f.exists():
            X = pd.concat([sets["combined"], F.shortcut_block(base)], axis=1)
            params = summary[f"{H}_lgbm_combined"]["selected"]
            booster, pr, auc = fit_lgbm(X[tr], y[tr], X[va], y[va], params)
            booster.save_model(str(MODELS / f"{H}_lgbm_shortcuts.txt"),
                               num_iteration=booster.best_iteration)
            np.save(f, booster.predict(X, num_iteration=booster.best_iteration).astype(np.float32))
            summary[f"{H}_lgbm_shortcuts"] = {"selected": params, "val_pr_auc": pr, "val_auroc": auc}
            summary_path.write_text(json.dumps(summary, indent=1))
            log(f"[{H}] shortcuts PR-AUC {pr:.4f}")
        del sets, X_values

    # row index for later steps
    df[["patient_id", "hospital", "hour", "split", "target", "in_training",
        "t_onset", "group", "hours_to_onset"]].to_parquet(ROOT / "data/processed/rows.parquet")
    (OUT / "variables_used.json").write_text(json.dumps({"used": variables, "dropped": dropped}, indent=1))
    log("done")


if __name__ == "__main__":
    main()
