"""Onset times, eligibility groups and the 12-hour training target (v3)."""

import numpy as np
import pandas as pd

from .config import LABEL_LEAD_HOURS, TARGET_HOURS
from .data_io import LABEL

NON_SEPTIC = "non_septic"
UNCERTAIN = "uncertain_onset"
ELIGIBLE = "eligible_septic"


def patient_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per patient with onset and eligibility group.

    With f = first record hour where SepsisLabel == 1 (0-based), onset is
    T_onset = f + 6. Groups (frozen):
      non_septic       label never 1
      uncertain_onset  label already 1 in the first row
      eligible_septic  label turns on after the first row
    fully_observed is a sensitivity flag: eligible and onset >= 12 h after
    the first row.
    """
    g = df.groupby("patient_id", sort=False)
    out = pd.DataFrame({
        "hospital": g["hospital"].first(),
        "n_hours": g.size(),
        "sepsis": g[LABEL].max().astype(int),
        "age": g["Age"].first(),
        "gender": g["Gender"].first(),
    })
    f = df[df[LABEL] == 1].groupby("patient_id")["hour"].min()
    out["label_on_hour"] = f
    out["t_onset"] = f + LABEL_LEAD_HOURS
    out["group"] = np.select(
        [out["sepsis"] == 0, out["label_on_hour"] == 0],
        [NON_SEPTIC, UNCERTAIN], default=ELIGIBLE)
    out["fully_observed"] = (out["group"] == ELIGIBLE) & (out["t_onset"] >= TARGET_HOURS)
    # kept for backward compatibility with earlier outputs
    out["onset_censored"] = out["group"] == UNCERTAIN
    return out.reset_index()


def add_target(df: pd.DataFrame, patients: pd.DataFrame) -> pd.DataFrame:
    """Add t_onset, group, target and in_training to the hourly table.

    target = 1 for T_onset - 12 <= hour < T_onset, else 0.
    in_training is False for hours at/after onset and for uncertain-onset
    patients, so the model never sees established sepsis.
    """
    p = patients.set_index("patient_id")[["t_onset", "group"]]
    out = df.join(p, on="patient_id")
    t = out["t_onset"]
    out["hours_to_onset"] = t - out["hour"]
    out["target"] = ((out["hours_to_onset"] > 0) & (out["hours_to_onset"] <= TARGET_HOURS)).astype(np.int8)
    out["in_training"] = (out["group"] != UNCERTAIN) & ~(out["hours_to_onset"] <= 0)
    return out
