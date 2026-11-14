"""Frozen-artifact LightGBM inference with causal, replay-safe features."""

import pickle
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from src import data_io as D, features as F


CRITICAL_VITALS = ("HR", "SBP", "Resp", "O2Sat", "Temp")
CRITICAL_FRESHNESS_HOURS = 2


class ModelUnavailable(RuntimeError):
    pass


def _logit(probability):
    p = np.clip(np.asarray(probability, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


class FrozenLightGBMEngine:
    """Loads only trusted local artifacts exported by script 11."""

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
        required = {"schema_version", "hospital", "variables", "features", "pools", "familiarity", "platt"}
        if self.bundle.get("schema_version") != 2 or self.bundle.get("hospital") != hospital:
            raise ModelUnavailable("artifact bundle schema or hospital does not match request")
        if not required.issubset(self.bundle):
            raise ModelUnavailable("artifact bundle is incomplete")
        if self.bundle["platt"]["coefficient"] <= 0:
            raise ModelUnavailable("artifact calibration is invalid")
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
            row.update({"patient_id": "inference_patient", "hour": h, "Age": age, "Gender": sex})
            for shortcut in D.SHORTCUTS:
                row[shortcut] = np.nan
            rows.append(row)
        return pd.DataFrame(rows)

    def _calibrate(self, raw_score: float) -> float:
        p = self.bundle["platt"]
        return float(1.0 / (1.0 + np.exp(-(p["coefficient"] * _logit(raw_score) + p["intercept"]))))

    def score(self, history: list[dict]) -> dict:
        df = self._frame(history)
        variables = self.bundle["variables"]
        base = F.causal_base(df, variables)
        X = F.assemble(base, self.bundle["pools"], "combined")[self.bundle["features"]]
        latest = X.iloc[[-1]]
        raw_score = float(self.model.predict(latest)[0])
        probability = self._calibrate(raw_score)
        contrib = self.model.predict(latest, pred_contrib=True)[0][:-1]
        top = np.argsort(np.abs(contrib))[::-1][:3]

        missing = []
        outside = []
        for i, variable in enumerate(variables):
            x, since = base["current"][-1, i], base["since"][-1, i]
            if variable in CRITICAL_VITALS and (np.isnan(x) or since > CRITICAL_FRESHNESS_HOURS):
                missing.append(variable)
            q01, q99 = self.bundle["familiarity"][variable]
            if not np.isnan(x) and (x < q01 or x > q99):
                outside.append(variable)

        familiarity = ("insufficient_data" if missing else
                       "unfamiliar_pattern" if len(outside) >= 2 else "within_validated_range")
        explanations = []
        for i in top:
            feature, value = str(X.columns[i]), float(latest.iloc[0, i])
            direction = "raised" if contrib[i] > 0 else "lowered"
            explanations.append({
                "feature": feature, "contribution": float(contrib[i]),
                "statement": f"{feature}={value:.2f} {direction} this prototype priority score.",
            })
        return {
            "priority_score": probability,
            "minimum_queue_priority": float(self.bundle["minimum_queue_priority"]),
            "model_name": self.bundle["model_name"],
            "model_version": self.bundle["model_version"],
            "familiarity": familiarity,
            "missing_critical_vitals": missing,
            "explanation": explanations,
        }
