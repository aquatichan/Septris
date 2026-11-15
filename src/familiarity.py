"""Distribution-shift guard for SignalBridge.

It flags a row as unfamiliar when a meaningful share of model features
lie outside the central range observed in the training hospital. It is not a
sepsis predictor and must never suppress a human review; it qualifies a score.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class FamiliarityGuard:
    columns: tuple[str, ...]
    lower: np.ndarray
    upper: np.ndarray
    row_threshold: float
    quantile: float

    def score(self, X: pd.DataFrame) -> np.ndarray:
        """Share of selected features outside training quantile bounds."""
        values = X.loc[:, self.columns].to_numpy(float)
        return ((values < self.lower) | (values > self.upper)).mean(axis=1)

    def unfamiliar(self, X: pd.DataFrame) -> np.ndarray:
        return self.score(X) > self.row_threshold

def fit_familiarity_guard(
    X_train: pd.DataFrame,
    X_validation: pd.DataFrame,
    *,
    columns: list[str] | None = None,
    quantile: float = 0.01,
    validation_abstention_rate: float = 0.05,
) -> FamiliarityGuard:
    """Freeze training bounds and the abstention rate on validation data only."""
    if not 0 < quantile < 0.5:
        raise ValueError("quantile must be between 0 and 0.5")
    if not 0 < validation_abstention_rate < 1:
        raise ValueError("validation_abstention_rate must be between 0 and 1")
    use = list(columns or X_train.columns)
    if not use:
        raise ValueError("at least one feature is required")
    if not set(use).issubset(X_train.columns) or not set(use).issubset(X_validation.columns):
        raise KeyError("guard columns must be in both training and validation data")
    lower = X_train.loc[:, use].quantile(quantile).to_numpy(float)
    upper = X_train.loc[:, use].quantile(1 - quantile).to_numpy(float)
    values = X_validation.loc[:, use].to_numpy(float)
    val_score = ((values < lower) | (values > upper)).mean(axis=1)
    threshold = float(np.quantile(val_score, 1 - validation_abstention_rate))
    return FamiliarityGuard(tuple(use), lower, upper, threshold, quantile)

def summary(guard: FamiliarityGuard, X: pd.DataFrame) -> dict[str, float]:
    """Serializable report for a model card and the clinician dashboard."""
    scores = guard.score(X)
    return {
        "median_out_of_range_share": float(np.median(scores)),
        "unfamiliar_share": float((scores > guard.row_threshold).mean()),
        "threshold": float(guard.row_threshold),
        "feature_quantile": float(guard.quantile),
        "n_features": len(guard.columns),
    }
