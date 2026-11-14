from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from api.schemas import ObservationIn


def payload(**updates):
    base = {
        "patient_id": "demo-1", "hospital": "A", "icu_hour": 4,
        "observed_at": datetime.now(timezone.utc), "values": {"HR": 95, "O2Sat": 97},
    }
    base.update(updates)
    return base


def test_rejects_impossible_vital_value():
    with pytest.raises(ValidationError, match="expected source-data range"):
        ObservationIn(**payload(values={"HR": 900}))


def test_rejects_future_observation():
    with pytest.raises(ValidationError, match="more than five minutes"):
        ObservationIn(**payload(observed_at=datetime.now(timezone.utc) + timedelta(minutes=6)))


def test_accepts_finite_partial_update():
    parsed = ObservationIn(**payload(values={"Lactate": 2.1}))
    assert parsed.values["Lactate"] == 2.1
