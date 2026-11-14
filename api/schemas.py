"""Public request/response schemas for the SEPTRIS replay API."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


VITAL_RANGES = {
    "HR": (10, 300), "O2Sat": (0, 100), "Temp": (20, 45),
    "SBP": (20, 300), "MAP": (10, 250), "DBP": (10, 200),
    "Resp": (1, 100), "EtCO2": (0, 150), "FiO2": (0.0, 1.0),
}


class ObservationIn(BaseModel):
    """One complete or partial chart update at a patient ICU hour."""

    model_config = ConfigDict(extra="forbid")
    patient_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    hospital: Literal["A", "B"]
    icu_hour: int = Field(ge=0, le=24 * 365)
    observed_at: datetime
    values: Dict[str, Optional[float]] = Field(default_factory=dict)
    age: Optional[float] = Field(default=None, ge=0, le=130)
    sex: Optional[int] = Field(default=None, ge=0, le=1)

    @field_validator("values")
    @classmethod
    def finite_values(cls, values):
        import math
        for key, value in values.items():
            if not key or len(key) > 64:
                raise ValueError("measurement names must be non-empty and at most 64 characters")
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{key} must be finite")
            if key in VITAL_RANGES and value is not None:
                low, high = VITAL_RANGES[key]
                if not low <= value <= high:
                    raise ValueError(f"{key} must be in the expected source-data range [{low}, {high}]")
        return values

    @field_validator("observed_at")
    @classmethod
    def not_far_future(cls, value):
        now = datetime.now(timezone.utc)
        stamp = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if stamp > now + timedelta(minutes=5):
            raise ValueError("observed_at cannot be more than five minutes in the future")
        return value


class ExplanationItem(BaseModel):
    feature: str
    contribution: float
    statement: str


class ScoreOut(BaseModel):
    patient_id: str
    hospital: Literal["A", "B"]
    icu_hour: int
    priority_score: float
    minimum_queue_priority: float
    model_name: str
    model_version: str
    familiarity: Literal["within_validated_range", "unfamiliar_pattern", "insufficient_data"]
    missing_critical_vitals: List[str]
    explanation: List[ExplanationItem]
    disclaimer: str = "This project is a prototype and is not medical advice."


class QueueItem(ScoreOut):
    queue_rank: int


class QueueOut(BaseModel):
    hospital: Literal["A", "B"]
    limit: int
    eligible_patients: int
    queue: List[QueueItem]
    policy: str
    disclaimer: str = "This project is a prototype and is not medical advice."


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewer_id: str = Field(min_length=1, max_length=128)
    reviewed_at: datetime
    action: Literal["opened_chart", "deferred", "escalated", "other"] = "opened_chart"
