"""Onset times from the official SepsisLabel."""

import pandas as pd

from .data_io import LABEL, LABEL_LEAD_HOURS

def patient_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per patient: stay length, sepsis status and onset hour.

    t_sepsis = first hour with SepsisLabel == 1, plus 6 hours.
    onset_censored is True when the label is already on at hour 0, meaning
    onset came within the first 6 ICU hours and the true lead is unknown.
    These patients stay in the data but are excluded from lead-time metrics.
    """
    g = df.groupby("patient_id", sort=False)
    out = pd.DataFrame({
        "hospital": g["hospital"].first(),
        "n_hours": g.size(),
        "sepsis": g[LABEL].max().astype(int),
    })
    first_pos = df[df[LABEL] == 1].groupby("patient_id")["hour"].min()
    out["label_on_hour"] = first_pos
    out["t_sepsis"] = first_pos + LABEL_LEAD_HOURS
    out["onset_censored"] = out["label_on_hour"].eq(0)
    return out.reset_index()
