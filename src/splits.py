"""Fixed, stratified, patient-level 70/15/15 splits for each hospital."""

import pandas as pd
from sklearn.model_selection import train_test_split

from .config import SEED


def make_splits(patients: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    """Split each hospital on its own, stratified on ever-septic.

    A->A, B->B, A->B and B->A therefore all test on the same fixed test
    patients of the target hospital.
    """
    parts = []
    for h, sub in patients.groupby("hospital"):
        ids, y = sub["patient_id"].to_numpy(), sub["sepsis"].to_numpy()
        train, rest, _, y_rest = train_test_split(
            ids, y, test_size=0.30, stratify=y, random_state=seed)
        val, test = train_test_split(
            rest, test_size=0.50, stratify=y_rest, random_state=seed)
        for name, chunk in (("train", train), ("val", val), ("test", test)):
            parts.append(pd.DataFrame({"patient_id": chunk, "hospital": h, "split": name}))
    splits = pd.concat(parts, ignore_index=True)
    return splits.merge(patients[["patient_id", "sepsis"]], on="patient_id")


def summarize(patients: pd.DataFrame, splits: pd.DataFrame) -> pd.DataFrame:
    """Patients, sepsis cases and sepsis rate for every hospital and split."""
    s = splits.groupby(["hospital", "split"]).agg(
        patients=("patient_id", "size"), sepsis_cases=("sepsis", "sum"))
    s["sepsis_rate_pct"] = (100 * s["sepsis_cases"] / s["patients"]).round(2)
    return s.reset_index()
