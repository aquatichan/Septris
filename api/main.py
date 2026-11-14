"""Run locally: uvicorn api.main:app --reload

This API is a replayable prototype, not a medical device or EHR integration.
"""

import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, status

from api.engine import FrozenLightGBMEngine, ModelUnavailable
from api.schemas import ObservationIn, QueueOut, QueueItem, ReviewIn, ScoreOut
from api.store import ReplayStore

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = Path(os.getenv("SEPTRIS_ARTIFACT_DIR", ROOT / "outputs" / "models"))
DB_PATH = Path(os.getenv("SEPTRIS_DB_PATH", ROOT / "outputs" / "septris_replay.sqlite3"))
MIN_PRIORITY = float(os.getenv("SEPTRIS_MIN_PRIORITY", "0.05"))

app = FastAPI(title="SEPTRIS Clinical Decision Support API", version="0.1.0")


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
    return {"status": "ok", "prototype": True, "models": availability}


@app.post("/v1/observations", response_model=ScoreOut, status_code=status.HTTP_201_CREATED)
def ingest(observation: ObservationIn):
    unknown = set(observation.values) - set(__import__("src.data_io", fromlist=["MEASURED"]).MEASURED)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown measurement fields: {sorted(unknown)}")
    payload = observation.model_dump(mode="json")
    payload["observed_at"] = iso(observation.observed_at)
    try:
        store().append_observation(payload)
        result = engine(observation.hospital).score(store().history(observation.patient_id))
    except ModelUnavailable as err:
        raise HTTPException(status_code=503, detail=f"scoring unavailable: {err}") from err
    except ValueError as err:
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
    candidates = []
    for score in store().candidates(hospital):
        if score["familiarity"] == "insufficient_data" or score["priority_score"] < MIN_PRIORITY:
            continue
        if store().is_snoozed(score["patient_id"], now):
            continue
        candidates.append(score)
    candidates.sort(key=lambda x: (-x["priority_score"], x["patient_id"]))
    queued = [{**x, "queue_rank": i + 1} for i, x in enumerate(candidates[:limit])]
    return {"hospital": hospital, "limit": limit, "eligible_patients": len(candidates),
            "queue": queued, "policy": "top priority scores; max 3 reviews; 12-hour review snooze"}


@app.get("/v1/patients/{patient_id}/timeline")
def timeline(patient_id: str):
    return {"patient_id": patient_id, "observations": store().history(patient_id)}


@app.post("/v1/patients/{patient_id}/review", status_code=status.HTTP_204_NO_CONTENT)
def review(patient_id: str, payload: ReviewIn):
    store().record_review(patient_id, payload.reviewer_id, iso(payload.reviewed_at), payload.action)
    return None
