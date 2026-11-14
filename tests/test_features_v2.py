"""Version 2 features: no future leakage, no NaN, chunking-safe."""

import numpy as np
import pandas as pd

from src import data_io as D, features as F, features_v2 as F2

VARS = [v for v in D.MEASURED if v != "EtCO2"]


def _build(df, train_mask=None):
    b = F.causal_base(df, VARS)
    m = np.ones(b["n"], bool) if train_mask is None else train_mask
    pools = F.fit_pools(b, m)
    vals = F.values_block(b, pools)
    xb = F2.extra_base(b)
    return b, pools, xb, F2.extra_block(b, xb, F2.fit_pools_v2(xb, m), vals)


def test_v2_no_future_leakage_and_no_nan(hourly):
    df = hourly.sort_values(["patient_id", "hour"]).reset_index(drop=True)
    b, pools, xb, X = _build(df)
    assert not X.isna().any().any()
    pools2 = F2.fit_pools_v2(xb, np.ones(b["n"], bool))
    rng = np.random.default_rng(3)
    ids = df["patient_id"].unique()
    for pid in rng.choice(ids, 40, replace=False):
        rows = np.flatnonzero(df["patient_id"].to_numpy() == pid)
        h = int(rng.integers(0, len(rows)))
        cut = df.iloc[rows[: h + 1]].reset_index(drop=True)
        bc = F.causal_base(cut, VARS)
        Xc = F2.extra_block(bc, F2.extra_base(bc), pools2, F.values_block(bc, pools))
        np.testing.assert_array_equal(X.iloc[rows[: h + 1]].to_numpy(), Xc.to_numpy(),
                                      err_msg=f"v2 leakage for {pid} at hour {h}")


def test_sofa_points():
    cur = {"Platelets": np.array([200, 120, 40, np.nan]), "Bilirubin_total": np.array([0.5, 1.5, 7, np.nan]),
           "Creatinine": np.array([1.0, 2.5, 6, np.nan]), "MAP": np.array([80, 65, 60, np.nan]),
           "FiO2": np.array([0.21, 0.5, 100, np.nan]), "O2Sat": np.array([98, 95, 90, np.nan])}
    p = F2.sofa_parts(cur)
    np.testing.assert_array_equal(p["sofa_coag"], [0, 1, 3, 0])
    np.testing.assert_array_equal(p["sofa_liver"], [0, 1, 3, 0])
    np.testing.assert_array_equal(p["sofa_renal"], [0, 2, 4, 0])
    np.testing.assert_array_equal(p["sofa_cardio"], [0, 1, 1, 0])
    np.testing.assert_array_equal(p["sofa_resp"], [0, 2, 3, 0])  # S/F 467, 190, 90


def test_v2_chunked_matches_single_pass(hourly):
    df = hourly.sort_values(["patient_id", "hour"]).reset_index(drop=True)
    b = F.causal_base(df, VARS)
    one, many = F2.extra_base(b), F2.extra_base(b, chunk_rows=500)
    for k in ("base_delta", "sofa_rise"):
        np.testing.assert_array_equal(one[k], many[k])
    for k in ("v24", "l24", "sofa"):
        for s in one[k]:
            np.testing.assert_array_equal(one[k][s], many[k][s])


import pytest
from pathlib import Path

REAL = Path(__file__).resolve().parents[1] / "data/processed/hourly.parquet"


@pytest.mark.skipif(not REAL.exists(), reason="real data not downloaded")
def test_v2_no_future_leakage_200_real_patients():
    df = pd.read_parquet(REAL).sort_values(["patient_id", "hour"]).reset_index(drop=True)
    df = df[df["patient_id"].isin(df["patient_id"].unique()[:1500])].reset_index(drop=True)
    b, pools, xb, X = _build(df)
    assert not X.isna().any().any()
    pools2 = F2.fit_pools_v2(xb, np.ones(b["n"], bool))
    rng = np.random.default_rng(5)
    ids = df["patient_id"].unique()
    for pid in rng.choice(ids, 200, replace=False):
        rows = np.flatnonzero(df["patient_id"].to_numpy() == pid)
        h = int(rng.integers(0, len(rows)))
        cut = df.iloc[rows[: h + 1]].reset_index(drop=True)
        bc = F.causal_base(cut, VARS)
        Xc = F2.extra_block(bc, F2.extra_base(bc), pools2, F.values_block(bc, pools))
        np.testing.assert_array_equal(X.iloc[rows[: h + 1]].to_numpy(), Xc.to_numpy())
