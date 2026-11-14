"""Step 11: export trusted local artifacts for the SEPTRIS replay API.

The bundle records exactly the feature order, training-hospital imputation
pools, and source-distribution familiarity ranges required for causal
single-patient replay. It is not a general interchange or user-upload format.
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

from src import config as C, data_io as D, features as F, labels as L

OUT = ROOT / "outputs"
MODELS = OUT / "models"


def main():
    df = pd.read_parquet(ROOT / "data/processed/hourly.parquet")
    df = df.sort_values(["patient_id", "hour"], kind="stable").reset_index(drop=True)
    patients = pd.read_csv(OUT / "patients.csv")
    df = L.add_target(df, patients)
    df["split"] = df["patient_id"].map(patients.set_index("patient_id")["split"])
    availability = pd.read_csv(OUT / "availability.csv")
    variables = [v for v in D.MEASURED
                 if v not in set(availability.loc[availability.flag_hospital_specific, "variable"])]
    base = F.causal_base(df, variables)
    hospital = df.hospital.to_numpy()
    split = df["split"].to_numpy()
    in_training = df.in_training.to_numpy(bool)
    selection = json.loads((OUT / "model_selection.json").read_text())

    for H in C.HOSPITALS:
        model_path = MODELS / f"{H}_lgbm_combined.txt"
        if not model_path.exists():
            raise FileNotFoundError(f"train model first: {model_path}")
        item = selection[f"{H}_lgbm_combined"]
        train = (hospital == H) & (split == "train") & in_training
        pools = F.fit_pools(base, train)
        familiarity = {}
        for j, variable in enumerate(variables):
            values = base["current"][train, j]
            values = values[~np.isnan(values)]
            familiarity[variable] = tuple(np.quantile(values, [0.01, 0.99])) if len(values) else (-np.inf, np.inf)
        digest = hashlib.sha256(model_path.read_bytes()).hexdigest()[:16]
        bundle = {
            "schema_version": 1,
            "model_name": "lgbm_combined",
            "model_version": f"{H}-lgbm-combined-{digest}",
            "hospital": H,
            "variables": variables,
            "features": item["features"],
            "pools": pools,
            "familiarity": familiarity,
        }
        path = MODELS / f"{H}_lgbm_combined.bundle.pkl"
        with path.open("wb") as f:
            pickle.dump(bundle, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"wrote {path} ({len(bundle['features'])} features)")


if __name__ == "__main__":
    main()
