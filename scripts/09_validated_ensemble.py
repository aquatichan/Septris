"""Step 09: source-validation-only LightGBM + temporal-GRU ensemble.

This script deliberately does not fit a flexible stacker.  For each source
hospital, patient-disjoint halves of the existing validation split are used:
one half fits independent Platt calibrators for the LightGBM and GRU scores;
the other selects a fixed convex blend by the actual 20-bed, 3-review
simulation.  Test patients are never used for calibration, alpha selection,
or model choice.

The output is a score for the existing evaluator, not a clinical prediction.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from src import config as C, simulation as S, labels as L

OUT = ROOT / "outputs"
SCORES = ROOT / "data/processed/scores"
NAME = "lgbm_gru_blend"
ALPHAS = np.linspace(0.0, 1.0, 11)  # alpha is the LightGBM weight


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def platt_fit_apply(train_score, train_y, score):
    """Fit a one-dimensional Platt calibrator and return calibrated scores."""
    model = LogisticRegression(C=1.0, max_iter=500, random_state=C.SEED)
    model.fit(logit(train_score).reshape(-1, 1), train_y)
    return model.predict_proba(logit(score).reshape(-1, 1))[:, 1], {
        "coefficient": float(model.coef_[0, 0]),
        "intercept": float(model.intercept_[0]),
        "n_rows": int(len(train_y)),
        "positive_rows": int(np.sum(train_y)),
    }


def patient_halves(patients, source):
    """Deterministic, group-stratified source-validation patient halves."""
    p = patients[(patients.hospital == source) & (patients.split == "val")].copy()
    rng = np.random.default_rng([C.SEED, ord(source), 91])
    calibration, selection = [], []
    for _, g in p.groupby("group", sort=True):
        ids = g.patient_id.to_numpy(copy=True)
        rng.shuffle(ids)
        cut = max(1, len(ids) // 2)
        calibration.extend(ids[:cut])
        selection.extend(ids[cut:])
    return set(calibration), set(selection)


def make_cohort(rows, patients, mask, score):
    """Create a simulator cohort from a patient-disjoint row subset."""
    r = rows[mask].copy()
    ids = r.patient_id.drop_duplicates().to_numpy()
    n_hours = r.groupby("patient_id", sort=False).size().reindex(ids).to_numpy()
    offsets = np.r_[0, np.cumsum(n_hours)[:-1]]
    p = patients.set_index("patient_id").loc[ids]
    return S.Cohort(
        n_hours=n_hours,
        t_onset=p.t_onset.to_numpy(float),
        group=p.group.to_numpy(object),
        offsets=offsets,
        scores={"blend": np.asarray(score)[mask]},
    )


def choose_alpha(rows, patients, source, selection_ids, calibrated_lgbm, calibrated_gru):
    """Pick the blend only by mean 6–12h early catches on selection patients."""
    is_selection = ((rows.hospital == source) & (rows.split == "val")
                    & rows.patient_id.isin(selection_ids)).to_numpy()
    candidates = []
    for alpha in ALPHAS:
        blend = alpha * calibrated_lgbm + (1.0 - alpha) * calibrated_gru
        cohort = make_cohort(rows, patients, is_selection, blend)
        values = [S.sweep(cohort, ["blend"], k=C.PRIMARY_K, seed=seed)[0]["blend"]
                  for seed in C.SIM_SEEDS]
        candidates.append({
            "alpha_lgbm": float(alpha),
            "alpha_gru": float(1.0 - alpha),
            "caught6": float(np.mean([x["caught6"] for x in values])),
            "false_per_shift": float(np.mean([x["false_per_shift"] for x in values])),
            "eligible": int(values[0]["eligible"]),
        })
    # Tie-breaking favors the simpler LightGBM model, then fewer false reviews.
    candidates.sort(key=lambda x: (x["caught6"], x["alpha_lgbm"], -x["false_per_shift"]),
                    reverse=True)
    return candidates[0], sorted(candidates, key=lambda x: x["alpha_lgbm"])


def main():
    rows = pd.read_parquet(ROOT / "data/processed/hourly.parquet")
    rows = rows.sort_values(["patient_id", "hour"], kind="stable").reset_index(drop=True)
    patients = pd.read_csv(OUT / "patients.csv")
    rows = L.add_target(rows, patients)
    rows["split"] = rows.patient_id.map(patients.set_index("patient_id").split)
    y = rows.target.to_numpy()
    report = {
        "name": NAME,
        "protocol": ("patient-disjoint source-validation calibration and alpha selection; "
                     "selection objective is simulated caught 6–12h early at 3 reviews/shift"),
        "alphas": ALPHAS.tolist(),
        "models": {},
    }

    for source in C.HOSPITALS:
        raw_lgbm = np.load(SCORES / f"{source}_lgbm_combined.npy")
        raw_gru = np.load(SCORES / f"{source}_temporal_gru.npy")
        cal_ids, select_ids = patient_halves(patients, source)
        cal = ((rows.hospital == source) & (rows.split == "val")
               & rows.patient_id.isin(cal_ids) & rows.in_training).to_numpy()
        if y[cal].sum() == 0 or len(np.unique(y[cal])) < 2:
            raise RuntimeError(f"{source}: calibration half lacks both outcome classes")
        lgbm, lgbm_info = platt_fit_apply(raw_lgbm[cal], y[cal], raw_lgbm)
        gru, gru_info = platt_fit_apply(raw_gru[cal], y[cal], raw_gru)
        chosen, grid = choose_alpha(rows, patients, source, select_ids, lgbm, gru)
        blend = chosen["alpha_lgbm"] * lgbm + chosen["alpha_gru"] * gru
        np.save(SCORES / f"{source}_{NAME}.npy", blend.astype(np.float32))
        report["models"][source] = {
            "calibration_patients": int(len(cal_ids)),
            "selection_patients": int(len(select_ids)),
            "lgbm_platt": lgbm_info,
            "gru_platt": gru_info,
            "chosen": chosen,
            "validation_grid": grid,
        }
        print(f"[{source}] alpha LGBM={chosen['alpha_lgbm']:.1f}, "
              f"GRU={chosen['alpha_gru']:.1f}; validation caught6={chosen['caught6']:.3f}",
              flush=True)

    (OUT / "ensemble_selection.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
