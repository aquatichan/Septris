"""Small guardrails for the isolated temporal GRU experiment."""

import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("temporal_gru", ROOT / "scripts" / "08_temporal_gru.py")
temporal_gru = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(temporal_gru)


def test_patient_bounds_never_cross_patient_ids():
    starts, ends = temporal_gru.patient_bounds(np.array(["a", "a", "b", "b", "b", "c"]))
    assert starts.tolist() == [0, 2, 5]
    assert ends.tolist() == [2, 5, 6]


def test_sequence_keeps_observation_mask_and_supervision_mask_separate():
    # Last row is post-onset/not supervised. It may be scored later, but never
    # contributes a training loss. A missing feature must remain distinguishable
    # from a measured zero through the observation-mask channel.
    base = {
        "current": np.array([[1.0, np.nan], [0.0, 2.0], [3.0, 4.0]], dtype=float),
        "since": np.array([[0.0, 24.0], [1.0, 0.0], [0.0, 0.0]], dtype=float),
        "age": np.array([50.0, 50.0, 50.0]),
        "gender": np.array([1.0, 1.0, 1.0]),
    }
    ds = temporal_gru.PatientSequences(
        base=base, target=np.array([0.0, 1.0, 0.0]),
        supervised=np.array([True, True, False]),
        bounds=(np.array([0]), np.array([3])), indices=np.array([0]),
        median=np.array([0.0, 0.0]), scale=np.array([1.0, 1.0]),
    )
    x, y, supervised = ds[0]
    assert x.shape == (3, 8)  # values + masks + gaps + age/sex
    assert x[0, 3] == 0.0  # second input was missing at hour 0
    assert x[1, 2] == 1.0  # a measured zero is still explicitly observed
    assert y.tolist() == [0.0, 1.0, 0.0]
    assert supervised.tolist() == [True, True, False]
