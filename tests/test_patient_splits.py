"""Splits, labels, eligibility and audit (v3 acceptance tests)."""

import numpy as np
import pandas as pd

from src import audit, labels, splits


def test_patient_table_groups(hourly):
    pt = labels.patient_table(hourly).set_index("patient_id")
    assert pt.loc["p000010", "t_onset"] == 26          # label on at 20, onset 6 h later
    assert pt.loc["p000010", "group"] == labels.ELIGIBLE
    assert pt.loc["p000000", "group"] == labels.UNCERTAIN  # positive in first row
    assert pt.loc["p000001", "group"] == labels.NON_SEPTIC
    assert bool(pt.loc["p000010", "fully_observed"])


def test_target_and_training_rows(hourly):
    pt = labels.patient_table(hourly)
    h = labels.add_target(hourly, pt)
    p = h[h["patient_id"] == "p000010"].set_index("hour")
    # target is 1 exactly for hours 14..25 (onset 26)
    assert p.loc[13, "target"] == 0 and p.loc[14, "target"] == 1 and p.loc[25, "target"] == 1
    assert not p.loc[26:, "in_training"].any()          # nothing at/after onset
    assert p.loc[:25, "in_training"].all()
    assert not h.loc[h["patient_id"] == "p000000", "in_training"].any()  # uncertain dropped
    assert (h.loc[h["group"] == labels.NON_SEPTIC, "target"] == 0).all()


def test_splits_disjoint_stratified_reproducible(hourly):
    pt = labels.patient_table(hourly)
    s1, s2 = splits.make_splits(pt), splits.make_splits(pt)
    pd.testing.assert_frame_equal(s1, s2)
    assert s1["patient_id"].is_unique and len(s1) == len(pt)
    rate = s1.groupby(["hospital", "split"])["sepsis"].mean()
    for h in ("A", "B"):
        r = rate[h]
        assert (r.max() - r.min()) <= 0.07  # 10 septic of 100: rounding only; the 1 pp rule is checked on real data below


def test_real_split_sepsis_share_within_1pp():
    """Acceptance test on the real audit output, when present."""
    from pathlib import Path
    f = Path(__file__).resolve().parents[1] / "outputs/split_summary.csv"
    if not f.exists():
        return
    s = pd.read_csv(f)
    for _, g in s.groupby("hospital"):
        assert g["sepsis_rate_pct"].max() - g["sepsis_rate_pct"].min() <= 1.0


def test_availability_flags(hourly):
    av = audit.variable_availability(hourly).set_index("variable")
    assert bool(av.loc["Lactate", "flag_hospital_specific"])  # absent at B only
    assert not bool(av.loc["HR", "flag_hospital_specific"])
    assert not bool(av.loc["Fibrinogen", "flag_hospital_specific"])  # rare at both
    assert bool(av.loc["Fibrinogen", "flag_hours_rule"])
