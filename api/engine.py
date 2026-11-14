"""Frozen-artifact LightGBM inference with causal, replay-safe features."""

import pickle
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from src import data_io as D, features as F


CRITICAL_VITALS = ("HR", "SBP", "Resp", "O2Sat", "Temp")


class ModelUnavailable(RuntimeError):
    pass


class FrozenLightGBMEngine:
    """Loads artifacts exported by scripts/11_export_model_bundle.py only."""

    def __init__(self, artifact_dir: str | Path, hospital: str):
        artifact_dir = Path(artifact_dir)
        bundle_path = artifact_dir / f"{hospital}_lgbm_combined.bundle.pkl"
        model_path = artifact_dir / f"{hospital}_lgbm_combined.txt"
        if not bundle_path.exists() or not model_path.exists():
            raise ModelUnavailable(
                f"Missing frozen artifact for hospital {hospital}; run scripts/11_export_model_bundle.py"
            )
        with bundle_path.open("rb") as f:
            self.bundle = pickle.load(f)
        if self.bundle.get("schema_version") != 1 or self.bundle.get("hospital") != hospital:
            raise ModelUnavailable("artifact bundle schema or hospital does not match request")
        self.model = lgb.Booster(model_file=str(model_path))
        self.hospital = hospital

    def _frame(self, history: list[dict]) -> pd.DataFrame:
        if not history:
            raise ValueError("no observation history")
        values = list(D.MEASURED)
        age = next((x.get("age") for x in reversed(history) if x.get("age") is not None), np.nan)
        sex = next((x.get("sex") for x in reversed(history) if x.get("sex") is not None), np.nan)
        rows = []
        by_hour = {x["icu_hour"]: x for x in history}
        for h in range(min(by_hour), max(by_hour) + 1):
            event = by_hour.get(h, {})
            row = {v: np.nan for v in values}
            row.update({k: v for k, v in event.get("values", {}).items() if k in row and v is not None})
            row.update({
                "patient_id": "inference_patient",
                "hour": h,
                "Age": age,
                "Gender": sex,
            })
            for shortcut in D.SHORTCUTS:
                row[shortcut] = np.nan
            rows.append(row)
        return pd.DataFrame(rows)

    def score(self, history: list[dict]) -> dict:
        df = self._frame(history)
        variables = self.bundle["variables"]
        base = F.causal_base(df, variables)
        X = F.assemble(base, self.bundle["pools"], "combined")
        X = X[self.bundle["features"]]
        latest = X.iloc[[-1]]
        probability = float(self.model.predict(latest)[0])
        contrib = self.model.predict(latest, pred_contrib=True)[0][:-1]
        top = np.argsort(np.abs(contrib))[::-1][:3]
        raw_latest = df.iloc[-1]
        missing = [v for v in CRITICAL_VITALS if v not in variables or pd.isna(raw_latest.get(v))]
        outside = []
        for i, v in enumerate(variables):
            x = base["current"][-1, i]
            q01, q99 = self.bundle["familiarity"][v]
            if not np.isnan(x) and (x < q01 or x > q99):
                outside.append(v)
        familiarity = ("insufficient_data" if missing else
                       "unfamiliar_pattern" if len(outside) >= 2 else "within_validated_range")
        explanations = []
        for i in top:
            feature = str(X.columns[i])
            val = float(latest.iloc[0, i])
            direction = "raised" if contrib[i] > 0 else "lowered"
            explanations.append({
                "feature": feature, "contribution": float(contrib[i]),
                "statement": f"{feature}={val:.2f} {direction} this prototype priority score.",
            })
        return {
            "priority_score": probability,
            "model_name": self.bundle["model_name"],
            "model_version": self.bundle["model_version"],
            "familiarity": familiarity,
            "missing_critical_vitals": missing,
            "explanation": explanations,
        }
