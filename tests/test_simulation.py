"""Acceptance tests for the review-slot sweep and alert classes."""

import numpy as np

from src import simulation as S
from src.labels import ELIGIBLE, NON_SEPTIC, UNCERTAIN


def _cohort(n=60, hours=40, seed=0):
    rng = np.random.default_rng(seed)
    n_hours = rng.integers(20, 60, n)
    group = np.array([ELIGIBLE if i % 6 == 0 else NON_SEPTIC for i in range(n)], object)
    group[1] = UNCERTAIN
    t_onset = np.where(group == ELIGIBLE, n_hours - 2, np.nan).astype(float)
    t_onset[1] = 3
    offsets = np.r_[0, np.cumsum(n_hours)[:-1]]
    total = int(n_hours.sum())
    scores = {"score": rng.random(total), "const": np.zeros(total)}
    return S.Cohort(n_hours, t_onset, group, offsets, scores)


def test_toy_patient_alert_classes():
    """Onset at hour 20; reviews at 5, 10, 16, 22 -> false, early6, early, late."""
    t_onset = np.array([20.0])
    group = np.array([ELIGIBLE], object)
    cls = S.classify(t_onset, group, np.zeros(4, int), np.array([5, 10, 16, 22]))
    assert list(cls) == [S.FALSE, S.EARLY6, S.EARLY, S.LATE]


def test_uncertain_and_non_septic_classes():
    cls = S.classify(np.array([np.nan, 3.0]), np.array([NON_SEPTIC, UNCERTAIN], object),
                     np.array([0, 1]), np.array([2, 1]))
    assert list(cls) == [S.FALSE, S.UNCERT]


def test_slot_offsets():
    assert S.slot_hours(3) == [0, 4, 8]
    assert S.slot_hours(1) == [0]
    assert S.slot_hours(2) == [0, 6]
    assert S.slot_hours(5) == [0, 2, 4, 7, 9]


def test_exactly_k_reviews_per_full_shift_and_snooze():
    c = _cohort()
    for k in (1, 3, 5):
        res, logs, info = S.sweep(c, ["random", "score"], k=k, seed=1)
        for pol, log in logs.items():
            # no patient reviewed twice within 12 hours
            for _, g in log.groupby("queue_pos"):
                t = np.sort(g["unit_hour"].to_numpy())
                assert (np.diff(t) >= 12).all()
            # with 20 beds and a 12 h snooze, every slot in a full shift fills
            per_shift = log.groupby(log["unit_hour"] // 12).size()
            full = per_shift.index[:-3]  # ignore the emptying tail
            assert (per_shift.loc[full] == k).all(), (pol, k)


def test_bed_schedule_identical_across_policies():
    c = _cohort()
    _, _, a = S.sweep(c, ["random"], k=3, seed=7)
    _, _, b = S.sweep(c, ["score", "const"], k=3, seed=7)
    np.testing.assert_array_equal(a["run_patients"], b["run_patients"])
    np.testing.assert_array_equal(a["admit"], b["admit"])


def test_every_patient_passes_through_once():
    c = _cohort()
    _, _, info = S.sweep(c, ["random"], k=3, seed=3)
    assert sorted(info["run_patients"]) == list(range(len(c.n_hours)))
