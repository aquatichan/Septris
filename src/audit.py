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
        for grp, n in p["group"].value_counts().items():
            add(h, f"group_{grp}", int(n))
        add(h, "group_fully_observed", int(p["fully_observed"].sum()))
        add(h, "positive_label_hours_pct", round(100 * sub[LABEL].mean(), 2))
        for q in (0.10, 0.5, 0.90):
            add(h, f"rows_per_patient_p{int(q * 100)}", float(p["n_hours"].quantile(q)))
        add(h, "rows_per_patient_min", int(p["n_hours"].min()))
        # rows are consecutive hours: ICULOS increases by exactly 1
        gaps = sub.groupby("patient_id")["ICULOS"].diff().dropna()
        add(h, "iculos_non_unit_steps", int((gaps != 1).sum()))
        add(h, "iculos_first_row_median", float(first["ICULOS"].median()))
        add(h, "age_median", float(first["Age"].median()))
        add(h, "age_max", float(first["Age"].max()))
        add(h, "age_share_at_max_pct", round(100 * (first["Age"] == first["Age"].max()).mean(), 3))
        add(h, "gender_values", "/".join(str(v) for v in sorted(first["Gender"].dropna().unique())))
        add(h, "male_pct_gender1", round(100 * first["Gender"].mean(), 2))
        fio2 = sub["FiO2"].dropna()
        add(h, "fio2_median", float(fio2.median()) if len(fio2) else float("nan"))
        add(h, "fio2_share_above_1_pct", round(100 * (fio2 > 1).mean(), 3) if len(fio2) else float("nan"))
        temp = sub["Temp"].dropna()
        add(h, "temp_median", float(temp.median()))
        for split, n in splits[splits["hospital"] == h].groupby("split").size().items():
            add(h, f"{split}_patients", int(n))
        for split, s2 in splits[splits["hospital"] == h].groupby("split"):
            add(h, f"{split}_sepsis_pct", round(100 * s2["sepsis"].mean(), 2))
    return pd.DataFrame(rows)
