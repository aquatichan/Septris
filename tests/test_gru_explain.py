"""The GRU explainer cites only measured values and gives at most three reasons."""

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from src import gru_explain as G  # noqa: E402


def test_reasons_cite_only_measured_values():
    mod, model, ck = G.load("A")
    v = ck["variables"]
    n_h = 10
    cur = np.full((n_h, len(v)), np.nan)
    cur[:, v.index("HR")] = np.linspace(90, 130, n_h)
    cur[:, v.index("Resp")] = 30
    since = np.full_like(cur, 48.0)
    since[:, [v.index("HR"), v.index("Resp")]] = 0.0
    base = {"current": cur, "since": since, "age": np.full(n_h, 70.0), "gender": np.ones(n_h), "variables": v}
    out = G.reasons(mod, model, ck, base, 0, n_h - 1)
    assert len(out) <= 3
    for r in out:
        if "latest" in r:
            assert "heart rate" in r or "respiratory rate" in r
