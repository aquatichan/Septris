"""Dataset audit: cohort summary and per-variable availability by hospital.

No modelling. Run this before training anything (brief section 4).
"""

import pandas as pd

from .data_io import LABEL, MEASURED, VITALS


def variable_availability(df: pd.DataFrame, rare_threshold_pct: float = 1.0) -> pd.DataFrame:
    """How often each measured variable is recorded at each hospital.

    Reports, per hospital, the share of patient-hours with a value and the
    share of patients with at least one value, plus two flags for the team
    to choose between:

    - flag_hours_rule: the brief's rule, recorded in fewer than 1% of
      patient-hours at either hospital. This also catches labs that are
      rare at BOTH hospitals (e.g. measured about once a day), which do not
      reveal the hospital.
    - flag_hospital_specific: recorded for fewer than 1% of patients at one
      hospital but not the other. This targets the actual risk, a missing
      flag that acts as a hidden hospital identifier.
    """
    rows = []
    hospitals = sorted(df["hospital"].unique())
    for var in MEASURED:
        row = {"variable": var, "kind": "vital" if var in VITALS else "lab"}
        for h in hospitals:
            sub = df[df["hospital"] == h]
            present = sub[var].notna()
            row[f"{h}_hours_pct"] = round(100 * present.mean(), 3)
            row[f"{h}_patients_pct"] = round(
                100 * present.groupby(sub["patient_id"]).any().mean(), 3)
        rows.append(row)
    t = pd.DataFrame(rows)
    hour_cols = [f"{h}_hours_pct" for h in hospitals]
    pat_cols = [f"{h}_patients_pct" for h in hospitals]
    t["flag_hours_rule"] = (t[hour_cols] < rare_threshold_pct).any(axis=1)
    rare_pat = t[pat_cols] < rare_threshold_pct
    t["flag_hospital_specific"] = rare_pat.any(axis=1) & ~rare_pat.all(axis=1)
    return t


def cohort_summary(df: pd.DataFrame, patients: pd.DataFrame,
                   splits: pd.DataFrame) -> pd.DataFrame:
    """Long-format audit table: hospital, metric, value."""
    rows = []

    def add(h, metric, value):
        rows.append({"hospital": h, "metric": metric, "value": value})

    for h, sub in df.groupby("hospital"):
        p = patients[patients["hospital"] == h]
        first = sub.groupby("patient_id").first()
        add(h, "patients", len(p))
        add(h, "patient_hours", len(sub))
        add(h, "sepsis_patients", int(p["sepsis"].sum()))
        add(h, "sepsis_pct", round(100 * p["sepsis"].mean(), 2))
        add(h, "sepsis_onset_in_first_6h", int(p["onset_censored"].sum()))
        add(h, "positive_label_hours_pct", round(100 * sub[LABEL].mean(), 2))
        for q in (0.25, 0.5, 0.75):
            add(h, f"icu_hours_p{int(q * 100)}", float(p["n_hours"].quantile(q)))
        add(h, "age_median", float(first["Age"].median()))
        add(h, "age_max", float(first["Age"].max()))
        add(h, "male_pct", round(100 * first["Gender"].mean(), 2))
        for split, n in splits[splits["hospital"] == h].groupby("split").size().items():
            add(h, f"{split}_patients", int(n))
    return pd.DataFrame(rows)
