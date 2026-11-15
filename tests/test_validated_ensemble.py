"""Guardrails for the patient-disjoint validated ensemble."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validated_ensemble", ROOT / "scripts" / "09_validated_ensemble.py")
ensemble = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ensemble)


def test_patient_halves_are_disjoint_and_cover_source_validation():
    patients = pd.DataFrame({
        "patient_id": ["A1", "A2", "A3", "A4", "A5", "B1"],
        "hospital": ["A", "A", "A", "A", "A", "B"],
        "split": ["val", "val", "val", "val", "val", "val"],
        "group": ["eligible_septic", "eligible_septic", "non_septic",
                  "non_septic", "non_septic", "eligible_septic"],
    })
    calibration, selection = ensemble.patient_halves(patients, "A")
    expected = set(patients.loc[patients.hospital == "A", "patient_id"])
    assert not calibration.intersection(selection)
    assert calibration.union(selection) == expected


def test_platt_calibration_returns_valid_probabilities():
    raw = np.array([0.02, 0.10, 0.20, 0.80, 0.90, 0.98])
    y = np.array([0, 0, 0, 1, 1, 1])
    calibrated, info = ensemble.platt_fit_apply(raw, y, raw)
    assert np.all((calibrated > 0) & (calibrated < 1))
    assert info["positive_rows"] == 3
    assert calibrated[-1] > calibrated[0]
