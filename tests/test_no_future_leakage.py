"""Acceptance tests: no future leakage, no NaN, no constant fill values."""

import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from src import data_io as D, features as F

VARS = [v for v in D.MEASURED if v != "EtCO2"]
REAL = Path(__file__).resolve().parents[1] / "data/processed/hourly.parquet"


def _patients(hourly, n=None):
    df = hourly.sort_values(["patient_id", "hour"]).reset_index(drop=True)
    if n:
        df = df[df["patient_id"].isin(df["patient_id"].unique()[:n])].reset_index(drop=True)
    return df


def _check_no_future(df, n_patients, rng):
    full = F.causal_base(df, VARS)
    pools = F.fit_pools(full, np.ones(full["n"], bool))
    X_full = F.assemble(full, pools, "combined")
    ids = df["patient_id"].unique()
    for pid in rng.choice(ids, size=min(n_patients, len(ids)), replace=False):
        rows = np.flatnonzero(df["patient_id"].to_numpy() == pid)
        h = int(rng.integers(0, len(rows)))
        cut = df.iloc[rows[: h + 1]].reset_index(drop=True)
        b = F.causal_base(cut, VARS)
        X_cut = F.assemble(b, pools, "combined")
        np.testing.assert_array_equal(X_full.iloc[rows[: h + 1]].to_numpy(), X_cut.to_numpy(),
                                      err_msg=f"future leakage for {pid} at hour {h}")


def test_no_future_leakage_synthetic(hourly):
    _check_no_future(_patients(hourly), 50, np.random.default_rng(1))


@pytest.mark.skipif(not REAL.exists(), reason="real data not downloaded")
def test_no_future_leakage_200_real_patients():
    df = _patients(pd.read_parquet(REAL), n=1500)
    _check_no_future(df, 200, np.random.default_rng(2))


def test_no_nan_reaches_models(hourly):
    df = _patients(hourly)
    b = F.causal_base(df, VARS)
    pools = F.fit_pools(b, np.ones(b["n"], bool))
    for fs in ("values", "missing", "combined"):
        assert not F.assemble(b, pools, fs).isna().any().any(), fs


@pytest.mark.skipif(not REAL.exists(), reason="real data not downloaded")
def test_no_constant_fill_value_real():
    """No values-only column repeats one value in >50% of rows unless 0/1."""
    df = _patients(pd.read_parquet(REAL), n=3000)
    b = F.causal_base(df, VARS)
    pools = F.fit_pools(b, np.ones(b["n"], bool))
    V = F.assemble(b, pools, "values")
    for c in V.columns:
        top = V[c].value_counts(normalize=True).iloc[0]
        is_flag = set(np.unique(V[c])) <= {0.0, 1.0}
        assert is_flag or top <= 0.5, (c, top)
