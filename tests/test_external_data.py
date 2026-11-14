import pandas as pd
import pytest

from src.external_data import require_clean_external_contract, validate_canonical_hourly


def frame():
    return pd.DataFrame({
        "patient_id": ["p1", "p1", "p2"],
        "hour": [0, 1, 0],
        "HR": [80, 81, 95],
        "SBP": [120, 118, 101],
        "Resp": [16, 18, 22],
        "O2Sat": [98, 98, 94],
        "Temp": [37.0, 37.2, 38.1],
        "WBC": [6.0, 6.1, 14.0],
        "Lactate": [1.0, 1.1, 2.2],
        "Creatinine": [0.8, 0.8, 1.3],
    })


def test_clean_external_contract_accepts_canonical_extract():
    audit = validate_canonical_hourly(frame(), "eicu")
    require_clean_external_contract(audit)
    assert audit.patients == 2
    assert audit.duplicate_patient_hours == 0


def test_external_contract_rejects_treatment_column():
    f = frame()
    f["antibiotic_order"] = 1
    audit = validate_canonical_hourly(f, "mimiciv")
    with pytest.raises(ValueError, match="leakage"):
        require_clean_external_contract(audit)


def test_external_contract_rejects_duplicate_patient_hour():
    f = pd.concat([frame(), frame().iloc[[0]]], ignore_index=True)
    audit = validate_canonical_hourly(f, "hirid")
    with pytest.raises(ValueError, match="duplicate"):
        require_clean_external_contract(audit)
