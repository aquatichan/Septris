"""Synthetic patients in the exact PhysioNet .psv format."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import data_io as D  # noqa: E402

COLUMNS = D.VITALS + D.LABS + D.DEMOGRAPHICS + [D.LABEL]


def make_patient(pid: str, n: int, label_on: int | None, rng, hospital_has_lactate=True):
    df = pd.DataFrame(np.nan, index=range(n), columns=COLUMNS)
    df["HR"] = rng.normal(85, 10, n)
    df["MAP"] = rng.normal(75, 8, n)
    df["SBP"] = rng.normal(120, 12, n)
    df["Resp"] = rng.normal(18, 3, n)
    df.loc[::4, "Temp"] = rng.normal(37, 0.5, len(df.loc[::4]))
    df.loc[::12, "WBC"] = rng.normal(9, 3, len(df.loc[::12]))
    if hospital_has_lactate:
        df.loc[::8, "Lactate"] = rng.normal(1.5, 0.5, len(df.loc[::8]))
    df["Age"], df["Gender"], df["HospAdmTime"] = 60.0, 1, -5.0
    df["ICULOS"] = np.arange(1, n + 1)
    df[D.LABEL] = 0
    if label_on is not None:
        df.loc[label_on:, D.LABEL] = 1
    return df


@pytest.fixture
def data_dir(tmp_path):
    rng = np.random.default_rng(0)
    for h, prefix, lac in (("A", "p0", True), ("B", "p1", False)):
        folder = tmp_path / D.HOSPITAL_DIRS[h]
        folder.mkdir()
        for i in range(100):
            sepsis = i % 10 == 0
            label_on = (0 if i == 0 else 20) if sepsis else None
            make_patient(f"{prefix}{i:05d}", 40, label_on, rng, lac).to_csv(
                folder / f"{prefix}{i:05d}.psv", sep="|", index=False, na_rep="NaN")
    return tmp_path


@pytest.fixture
def hourly(data_dir):
    return pd.concat([D.load_hospital(data_dir, h) for h in ("A", "B")], ignore_index=True)
