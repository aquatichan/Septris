"""Tests on small synthetic files in the exact PhysioNet .psv format."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import audit, data_io as D, labels, splits  # noqa: E402

COLUMNS = D.VITALS + D.LABS + D.DEMOGRAPHICS + [D.LABEL]


def _write_patient(folder: Path, pid: str, n: int, label_on: int | None,
                   rng: np.random.Generator, drop_lactate: bool = False) -> None:
    df = pd.DataFrame(np.nan, index=range(n), columns=COLUMNS)
    df["HR"] = rng.normal(85, 10, n)
    df["MAP"] = rng.normal(75, 8, n)
    if not drop_lactate:
        df.loc[::8, "Lactate"] = rng.normal(1.5, 0.5, len(df.loc[::8]))
    df["Age"], df["Gender"], df["HospAdmTime"] = 60.0, 1, -5.0
    df["ICULOS"] = np.arange(1, n + 1)
    df[D.LABEL] = 0
    if label_on is not None:
        df.loc[label_on:, D.LABEL] = 1
    df.to_csv(folder / f"{pid}.psv", sep="|", index=False, na_rep="NaN")


@pytest.fixture
def data_dir(tmp_path):
    rng = np.random.default_rng(0)
    for h, prefix, drop_lac in (("A", "p0", False), ("B", "p1", True)):
        folder = tmp_path / D.HOSPITAL_DIRS[h]
        folder.mkdir()
        for i in range(100):
            sepsis = i % 10 == 0  # 10% sepsis
            label_on = (0 if i == 0 else 20) if sepsis else None
            _write_patient(folder, f"{prefix}{i:05d}", 40, label_on, rng, drop_lac)
    return tmp_path


def test_load_and_patient_table(data_dir):
    df = D.load_hospital(data_dir, "A")
    assert df["patient_id"].nunique() == 100
    assert (df.groupby("patient_id")["hour"].min() == 0).all()
    pt = labels.patient_table(df)
    sep = pt[pt["sepsis"] == 1].set_index("patient_id")
    assert len(sep) == 10
    assert sep.loc["p000010", "t_sepsis"] == 26  # label on at 20, onset 6 h later
    assert bool(sep.loc["p000000", "onset_censored"])  # label on at hour 0
    assert pt.loc[pt["sepsis"] == 0, "t_sepsis"].isna().all()


def test_splits_are_disjoint_stratified_and_reproducible(data_dir):
    df = pd.concat([D.load_hospital(data_dir, h) for h in ("A", "B")])
    pt = labels.patient_table(df)
    s1, s2 = splits.make_splits(pt, seed=42), splits.make_splits(pt, seed=42)
    pd.testing.assert_frame_equal(s1, s2)
    assert s1["patient_id"].is_unique
    assert len(s1) == len(pt)
    counts = s1.groupby(["hospital", "split"]).size()
    assert counts[("A", "train")] == 70 and counts[("A", "test")] == 15
    # every split keeps sepsis cases, and no patient crosses hospitals
    assert (s1.groupby(["hospital", "split"])["sepsis"].sum() > 0).all()
    assert (s1["patient_id"].str[1] == s1["hospital"].map({"A": "0", "B": "1"})).all()


def test_availability_flags_hospital_specific_variable(data_dir):
    df = pd.concat([D.load_hospital(data_dir, h) for h in ("A", "B")])
    av = audit.variable_availability(df).set_index("variable")
    assert av.loc["HR", "A_patients_pct"] == 100
    assert av.loc["Lactate", "B_patients_pct"] == 0
    assert bool(av.loc["Lactate", "flag_hospital_specific"])  # absent at B only
    assert not bool(av.loc["HR", "flag_hospital_specific"])
    # a variable never recorded anywhere is rare, but not a hospital identifier
    assert not bool(av.loc["Fibrinogen", "flag_hospital_specific"])
    assert bool(av.loc["Fibrinogen", "flag_hours_rule"])


def test_cohort_summary(data_dir):
    df = pd.concat([D.load_hospital(data_dir, h) for h in ("A", "B")])
    pt = labels.patient_table(df)
    sp = splits.make_splits(pt)
    c = audit.cohort_summary(df, pt, sp).set_index(["hospital", "metric"])["value"]
    assert c[("A", "patients")] == 100 and c[("B", "sepsis_patients")] == 10
    assert c[("A", "sepsis_onset_in_first_6h")] == 1
