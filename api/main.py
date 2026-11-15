"""Run locally only: uvicorn api.main:app --host 127.0.0.1 --port 8000

This API is a replayable prototype, not a medical device or EHR integration.
"""

import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from sqlite3 import IntegrityError

from fastapi import FastAPI, HTTPException, status

from api.engine import FrozenLightGBMEngine, ModelUnavailable
from api.schemas import ObservationIn, QueueOut, ReviewIn, ScoreOut
from api.store import ReplayStore
from src.data_io import MEASURED

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = Path(os.getenv("SEPTRIS_ARTIFACT_DIR", ROOT / "outputs" / "models"))
DB_PATH = Path(os.getenv("SEPTRIS_DB_PATH", ROOT / "outputs" / "septris_replay.sqlite3"))
_override = os.getenv("SEPTRIS_MIN_PRIORITY")
MIN_PRIORITY_OVERRIDE = float(_override) if _override is not None else None
MAX_OBSERVATION_AGE_HOURS = float(os.getenv("SEPTRIS_MAX_OBSERVATION_AGE_HOURS", "2"))

app = FastAPI(title="SEPTRIS Clinical Decision Support API", version="0.2.0")


@lru_cache
def store():
    return ReplayStore(DB_PATH)


@lru_cache
def engine(hospital: str):
    return FrozenLightGBMEngine(ARTIFACT_DIR, hospital)


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


@app.get("/health")
def health():
    availability = {}
    for hospital in ("A", "B"):
        try:
            e = engine(hospital)
            availability[hospital] = {"ready": True, "model_version": e.bundle["model_version"]}
        except ModelUnavailable as err:
            availability[hospital] = {"ready": False, "reason": str(err)}
    return {"status": "ok", "prototype": True, "intended_loopback_only": True, "models": availability}


@app.post("/v1/observations", response_model=ScoreOut, status_code=status.HTTP_201_CREATED)
def ingest(observation: ObservationIn):
    unknown = set(observation.values) - set(MEASURED)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown measurement fields: {sorted(unknown)}")
    payload = observation.model_dump(mode="json")
    payload["observed_at"] = iso(observation.observed_at)
    try:
        active_engine = engine(observation.hospital)  # fail before mutating replay state
        store().validate_append(payload)
        result = active_engine.score(store().history(observation.patient_id) + [payload])
        store().append_observation(payload)
    except ModelUnavailable as err:
        raise HTTPException(status_code=503, detail=f"scoring unavailable: {err}") from err
    except (ValueError, IntegrityError) as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    score = {
        "patient_id": observation.patient_id, "hospital": observation.hospital,
        "icu_hour": observation.icu_hour, "observed_at": payload["observed_at"], **result,
    }
    store().save_score(score)
    return score


@app.get("/v1/queue", response_model=QueueOut)
def queue(hospital: str, limit: int = 3, as_of: datetime | None = None):
    if hospital not in ("A", "B") or not 1 <= limit <= 3:
        raise HTTPException(status_code=422, detail="hospital must be A/B and limit must be 1–3")
    now = iso(as_of or datetime.now(timezone.utc))
    reference = datetime.fromisoformat(now.replace("Z", "+00:00"))
    candidates = []
    for score in store().candidates(hospital):
        priority_floor = MIN_PRIORITY_OVERRIDE if MIN_PRIORITY_OVERRIDE is not None else score["minimum_queue_priority"]
        if score["familiarity"] == "insufficient_data" or score["priority_score"] < priority_floor:
            continue
        observed = datetime.fromisoformat(score["observed_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        age_seconds = (reference - observed).total_seconds()
        if age_seconds < 0 or age_seconds > MAX_OBSERVATION_AGE_HOURS * 3600:
            continue
        if store().is_snoozed(score["patient_id"], now):
            continue
        candidates.append(score)
    candidates.sort(key=lambda x: (-x["priority_score"], x["patient_id"]))
    queued = [{**x, "queue_rank": i + 1} for i, x in enumerate(candidates[:limit])]
    return {"hospital": hospital, "limit": limit, "eligible_patients": len(candidates),
            "queue": queued, "policy": "calibrated source-validation threshold; max 3 reviews; 12-hour review snooze"}


@app.get("/v1/patients/{patient_id}/timeline")
def timeline(patient_id: str):
    return {"patient_id": patient_id, "observations": store().history(patient_id)}


@app.post("/v1/patients/{patient_id}/review", status_code=status.HTTP_204_NO_CONTENT)
def review(patient_id: str, payload: ReviewIn):
    try:
        store().record_review(patient_id, payload.reviewer_id, iso(payload.reviewed_at), payload.action)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    return None
