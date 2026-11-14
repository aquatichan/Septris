"""Vectorized PhysioNet 2019 utility, checked against the official code.

The official per-row loop (vendor/physionet_2019_evaluation, BSD-2) is too
slow to sweep thresholds over 1.5M rows. This reproduces it exactly;
tests/test_utility.py compares the two on random patients.
"""

import numpy as np

DT_EARLY, DT_OPTIMAL, DT_LATE = -12, -6, 3.0
MAX_U_TP, MIN_U_FN, U_FP, U_TN = 1, -2, -0.05, 0


def _row_utility(labels_onset, hour, pred, septic):
    """Utility per row given t_sepsis (official definition) per row."""
    t_sepsis = labels_onset
    m1 = MAX_U_TP / (DT_OPTIMAL - DT_EARLY)
    b1 = -m1 * DT_EARLY
    m2 = -MAX_U_TP / (DT_LATE - DT_OPTIMAL)
    b2 = -m2 * DT_LATE
    m3 = MIN_U_FN / (DT_LATE - DT_OPTIMAL)
    b3 = -m3 * DT_OPTIMAL
    d = hour - t_sepsis
    u = np.zeros(len(hour))
    inwin = ~septic | (d <= DT_LATE)
    tp = septic & pred & inwin
    u = np.where(tp & (d <= DT_OPTIMAL), np.maximum(m1 * d + b1, U_FP), u)
    u = np.where(tp & (d > DT_OPTIMAL), m2 * d + b2, u)
    u = np.where(~septic & pred, U_FP, u)
    fn = septic & ~pred & inwin
    u = np.where(fn & (d > DT_OPTIMAL), m3 * d + b3, u)
    return np.where(inwin, u, 0.0)


def t_sepsis_rows(label_first_hour: np.ndarray) -> np.ndarray:
    """Official t_sepsis = argmax(labels) - dt_optimal (NaN if non-septic)."""
    return label_first_hour - DT_OPTIMAL


def normalized_utility(hour, t_sepsis, n_hours, pred) -> float:
    """Normalized utility over all rows (one cohort)."""
    septic = ~np.isnan(t_sepsis)
    ts = np.where(septic, t_sepsis, np.inf)
    obs = _row_utility(ts, hour, pred.astype(bool), septic).sum()
    best_pred = septic & (hour >= ts + DT_EARLY) & (hour <= ts + DT_LATE)
    best = _row_utility(ts, hour, best_pred, septic).sum()
    inaction = _row_utility(ts, hour, np.zeros(len(hour), bool), septic).sum()
    return float((obs - inaction) / (best - inaction))
