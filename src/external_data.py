"""External-data contract for SEPTRIS validation.

These functions deliberately accept only a locally prepared canonical extract.
They never download credentialed data, infer a sepsis label, or merge a new
hospital into development training data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data_io import MEASURED

REQUIRED = ("patient_id", "hour")
PROHIBITED_TREATMENT_PATTERN = re.compile(
    r"(antibiotic|culture|vasopressor|ventilat|intubat|peep|tidal|fluid|"
    r"treatment|order|bundle|sepsislabel)",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class ExternalAudit:
    source: str
    patients: int
    rows: int
    hours: int
    measured_columns: list[str]
    missing_required: list[str]
    prohibited_columns: list[str]
    duplicate_patient_hours: int
    time_reversals: int
    coverage: dict[str, float]


def prohibited_columns(columns) -> list[str]:
    """Fields that would create post-treatment or clinician-action leakage."""
    return sorted(c for c in columns if PROHIBITED_TREATMENT_PATTERN.search(str(c)))


def validate_canonical_hourly(frame: pd.DataFrame, source: str) -> ExternalAudit:
    """Audit a canonical hourly extract before any model sees it.

    Required fields are patient_id and hour. Values must already be in the
    PhysioNet-compatible units documented in external_validation_protocol.md.
    This function does not impute, construct labels, or discard problematic
    patients, because those choices must be reported.
    """
    missing = [c for c in REQUIRED if c not in frame.columns]
    if missing:
        raise ValueError(f"{source}: missing canonical columns {missing}")
    if frame.empty:
        raise ValueError(f"{source}: empty external extract")
    f = frame.copy()
    f["hour"] = pd.to_numeric(f["hour"], errors="coerce")
    if f["hour"].isna().any() or (f["hour"] < 0).any() or (f["hour"] % 1 != 0).any():
        raise ValueError(f"{source}: hour must be a non-negative integer")
    duplicate = int(f.duplicated(["patient_id", "hour"]).sum())
    ordered = f.sort_values(["patient_id", "hour"], kind="stable")
    reversals = int((ordered.groupby("patient_id", sort=False)["hour"].diff() <= 0).fillna(False).sum())
    measured = [c for c in MEASURED if c in f.columns]
    coverage = {c: float(f[c].notna().mean()) for c in measured}
    prohibited = prohibited_columns(f.columns)
    return ExternalAudit(
        source=source,
        patients=int(f["patient_id"].nunique()),
        rows=int(len(f)),
        hours=int(f["hour"].max()) + 1,
        measured_columns=measured,
        missing_required=missing,
        prohibited_columns=prohibited,
        duplicate_patient_hours=duplicate,
        time_reversals=reversals,
        coverage=coverage,
    )


def require_clean_external_contract(audit: ExternalAudit):
    """Hard-stop conditions before frozen-model scoring."""
    problems = []
    if audit.prohibited_columns:
        problems.append(f"treatment/label leakage columns present: {audit.prohibited_columns}")
    if audit.duplicate_patient_hours:
        problems.append(f"{audit.duplicate_patient_hours} duplicate patient-hour rows")
    if audit.time_reversals:
        problems.append(f"{audit.time_reversals} non-increasing patient-hour rows")
    if len(audit.measured_columns) < 8:
        problems.append("fewer than 8 compatible vitals/labs")
    if problems:
        raise ValueError(f"{audit.source}: external contract rejected; " + "; ".join(problems))


def cohort_coverage_table(audit: ExternalAudit) -> pd.DataFrame:
    return pd.DataFrame(
        [{"source": audit.source, "variable": k, "observed_row_pct": 100 * v}
         for k, v in audit.coverage.items()]
    )
