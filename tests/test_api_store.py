from datetime import datetime, timedelta, timezone

import pytest

from api.store import ReplayStore


def event(patient_id="p1", hour=0):
    return {"patient_id": patient_id, "hospital": "A", "icu_hour": hour,
            "observed_at": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            "values": {"HR": 90}}


def test_monotonic_patient_history_and_hashed_audit(tmp_path):
    store = ReplayStore(tmp_path / "replay.sqlite3")
    store.append_observation(event(hour=0))
    store.append_observation(event(hour=1))
    assert [x["icu_hour"] for x in store.history("p1")] == [0, 1]
    with pytest.raises(ValueError):
        store.append_observation(event(hour=0))


def test_review_snooze_is_twelve_hours(tmp_path):
    store = ReplayStore(tmp_path / "replay.sqlite3")
    store.append_observation(event())
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store.record_review("p1", "nurse@example.test", t0.isoformat(), "opened_chart")
    assert store.is_snoozed("p1", (t0 + timedelta(hours=11, minutes=59)).isoformat())
    assert not store.is_snoozed("p1", (t0 + timedelta(hours=12)).isoformat())


def test_score_storage_replaces_latest_score(tmp_path):
    store = ReplayStore(tmp_path / "replay.sqlite3")
    score = {"patient_id": "p1", "hospital": "A", "icu_hour": 2,
             "observed_at": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
             "priority_score": 0.4}
    store.save_score(score)
    score["priority_score"] = 0.8
    store.save_score(score)
    assert store.candidates("A")[0]["priority_score"] == 0.8


def test_rejects_patient_hospital_switch_and_duplicate_hour(tmp_path):
    store = ReplayStore(tmp_path / "replay.sqlite3")
    store.append_observation(event(hour=0))
    switched = event(hour=1)
    switched["hospital"] = "B"
    with pytest.raises(ValueError, match="different source hospital"):
        store.append_observation(switched)
    with pytest.raises(ValueError, match="strictly newer"):
        store.append_observation(event(hour=0))


def test_rejects_review_for_unknown_patient(tmp_path):
    store = ReplayStore(tmp_path / "replay.sqlite3")
    with pytest.raises(ValueError, match="unknown patient"):
        store.record_review("not-present", "reviewer", datetime.now(timezone.utc).isoformat(), "opened_chart")


def test_audit_contains_keyed_hashes_not_raw_identifier(tmp_path):
    store = ReplayStore(tmp_path / "replay.sqlite3")
    store.append_observation(event(patient_id="identifiable-patient", hour=0))
    with store.connect() as con:
        row = con.execute("SELECT patient_id_hash, payload_hash FROM audit_events").fetchone()
    assert "identifiable-patient" not in row["patient_id_hash"]
    assert "identifiable-patient" not in row["payload_hash"]
