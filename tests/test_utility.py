"""The vectorized utility must equal the official per-row implementation."""

import numpy as np

from src import utility as U
from vendor.physionet_2019_evaluation.evaluate_sepsis_score import compute_prediction_utility


def test_matches_official_on_random_patients():
    rng = np.random.default_rng(0)
    for _ in range(300):
        n = int(rng.integers(8, 80))
        labels = np.zeros(n, int)
        if rng.random() < 0.4:
            labels[int(rng.integers(0, n)):] = 1
        pred = (rng.random(n) < rng.random()).astype(int)
        official = compute_prediction_utility(labels, pred)
        septic = labels.any()
        ts = np.full(n, (np.argmax(labels) - U.DT_OPTIMAL) if septic else np.inf)
        ours = U._row_utility(ts, np.arange(n), pred.astype(bool), np.full(n, septic)).sum()
        assert np.isclose(official, ours), (official, ours)
