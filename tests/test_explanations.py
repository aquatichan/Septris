"""The "why now" line never cites a gap-filled value."""

import numpy as np

from src import data_io as D, explanations as E, features as F

VARS = [v for v in D.MEASURED if v != "EtCO2"]


def test_never_cites_gap_filled_values(hourly):
    df = hourly.sort_values(["patient_id", "hour"]).reset_index(drop=True)
    b = F.causal_base(df, VARS)
    X = F.assemble(b, F.fit_pools(b, np.ones(b["n"], bool)), "combined")
    cols = list(X.columns)
    for row in range(0, b["n"], 97):
        for i, c in enumerate(cols):
            p = E.phrase(c, X.iloc[row], b, row)
            if p is None or c.startswith("m_"):
                continue
            var = c.split("_")[0] if c != "shock_index" else "HR"
            if c in VARS:
                assert not np.isnan(b["current"][row, VARS.index(c)]), (c, row)
            for stat in ("min6", "max6", "mean6"):
                if c.endswith(stat):
                    k = b["vitals"].index(c[: -len(stat) - 1])
                    assert not np.isnan(b["roll"][stat[:-1]][row, k]), (c, row)


def test_why_now_template():
    s = E.why_now(None, np.array([-1.0]), ["age"], {"variables": []}, 0)
    assert s.endswith("These are model associations, not a diagnosis.")
