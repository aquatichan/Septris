"""Step 11: export trusted local artifacts for the SEPTRIS replay API.

The bundle preserves feature order, source-training imputation pools,
source-distribution familiarity ranges, source-validation Platt calibration,
and the validation-chosen utility threshold. It is never an uploaded format.
"""

import hashlib
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from src import config as C, data_io as D, features as F, labels as L

OUT = ROOT / "outputs"
MODELS = OUT / "models"
RES = OUT / "results"


def logit(score):
    p = np.clip(np.asarray(score, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def calibrated_threshold(raw_threshold, calibrator):
    z = calibrator["coefficient"] * logit(raw_threshold) + calibrator["intercept"]
    return float(1.0 / (1.0 + np.exp(-z)))


def main():
    df = pd.read_parquet(ROOT / "data/processed/hourly.parquet")
    df = df.sort_values(["patient_id", "hour"], kind="stable").reset_index(drop=True)
    patients = pd.read_csv(OUT / "patients.csv")
    df = L.add_target(df, patients)
    df["split"] = df["patient_id"].map(patients.set_index("patient_id")["split"])
    availability = pd.read_csv(OUT / "availability.csv")
    utility_path = RES / "utility_scores.csv"
    if not utility_path.exists():
        raise FileNotFoundError("run evaluation first; utility_scores.csv supplies the frozen queue threshold")
    utility = pd.read_csv(utility_path)
    variables = [v for v in D.MEASURED
                 if v not in set(availability.loc[availability.flag_hospital_specific, "variable"])]
    base = F.causal_base(df, variables)
    hospital = df.hospital.to_numpy()
    split = df["split"].to_numpy()
    in_training = df.in_training.to_numpy(bool)
    y = df.target.to_numpy()
    selection = json.loads((OUT / "model_selection.json").read_text())

    for H in C.HOSPITALS:
        model_path = MODELS / f"{H}_lgbm_combined.txt"
        score_path = ROOT / "data/processed/scores" / f"{H}_lgbm_combined.npy"
        if not model_path.exists() or not score_path.exists():
            raise FileNotFoundError(f"train model and scores first for hospital {H}")
        item = selection[f"{H}_lgbm_combined"]
        train = (hospital == H) & (split == "train") & in_training
        val = (hospital == H) & (split == "val") & in_training
        raw_scores = np.load(score_path)
        calibrator_model = LogisticRegression(C=1.0, max_iter=500, random_state=C.SEED)
        calibrator_model.fit(logit(raw_scores[val]).reshape(-1, 1), y[val])
        coefficient = float(calibrator_model.coef_[0, 0])
        if coefficient <= 0:
            raise RuntimeError(f"{H}: non-monotonic validation calibration; refusing to export")
        calibrator = {"coefficient": coefficient, "intercept": float(calibrator_model.intercept_[0]),
                      "n_rows": int(val.sum()), "positive_rows": int(y[val].sum())}
        threshold_rows = utility[(utility.train == H) & (utility.test == H) &
                                 (utility.model == "lgbm_combined")]
        if threshold_rows.empty:
            raise RuntimeError(f"{H}: missing home-hospital utility threshold")
        raw_threshold = float(threshold_rows.iloc[0].threshold)
        pools = F.fit_pools(base, train)
        familiarity = {}
        for j, variable in enumerate(variables):
            values = base["current"][train, j]
            values = values[~np.isnan(values)]
            familiarity[variable] = tuple(np.quantile(values, [0.01, 0.99])) if len(values) else (-np.inf, np.inf)
        model_sha256 = hashlib.sha256(model_path.read_bytes()).hexdigest()
        bundle = {
            "schema_version": 2,
            "model_name": "lgbm_combined",
            "model_version": f"{H}-lgbm-combined-{model_sha256[:16]}",
            "model_sha256": model_sha256,
            "hospital": H,
            "variables": variables,
            "features": item["features"],
            "pools": pools,
            "familiarity": familiarity,
            "platt": calibrator,
            "minimum_queue_priority": calibrated_threshold(raw_threshold, calibrator),
            "raw_utility_threshold": raw_threshold,
        }
        path = MODELS / f"{H}_lgbm_combined.bundle.pkl"
        with path.open("wb") as f:
            pickle.dump(bundle, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"wrote {path} ({len(bundle['features'])} features; threshold={bundle['minimum_queue_priority']:.3f})")


if __name__ == "__main__":
    main()
