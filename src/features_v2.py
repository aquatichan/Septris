"""Version 2 features, added after version 1's test results (post hoc).

Version 1 (src/features.py) stays frozen. These extra columns use only
rows up to and including hour h of the same patient:

- partial SOFA score from recorded values (platelets, bilirubin,
  creatinine, MAP, SpO2/FiO2), its change from the lowest score in the last
  24 hours, and each component;
- 24-hour min/max/mean of real vital-sign readings;
- 24-hour max/min of key labs;
- change from the patient's own first recorded value (baseline).

Gaps follow version 1's rules: rolling stats fall back to the filled current
value, and baseline changes are drawn from the training hospital's values
with the same hash, so no NaN reaches a model.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from .features import _fill

WIN = 24
KEY_LABS = ["Lactate", "WBC", "Creatinine", "Platelets", "Bilirubin_total", "BUN"]
BASELINE_VARS = ["HR", "MAP", "Resp", "Temp", "O2Sat", "SBP"] + KEY_LABS


def _lag_stack(x: np.ndarray, grp: np.ndarray, win: int) -> np.ndarray:
    """(win, n, m) array of x at lags 0..win-1 within the patient, NaN across patients."""
    n = len(x)
    out = np.full((win, n, x.shape[1]), np.nan, np.float32)
    for lag in range(win):
        if lag == 0:
            out[0] = x
            continue
        sh = np.full_like(out[0], np.nan)
        sh[lag:] = x[:-lag]
        same = np.zeros(n, bool)
        same[lag:] = grp[lag:] == grp[:-lag]
        sh[~same] = np.nan
        out[lag] = sh
    return out


def _nanstat(stack, fn):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return fn(stack, axis=0).astype(np.float32)


def _points(x, cuts, pts):
    """Score x by thresholds (ascending cuts); NaN scores 0."""
    out = np.zeros(len(x), np.float32)
    with np.errstate(invalid="ignore"):
        for c, p in zip(cuts, pts):
            out = np.where(x >= c, p, out)
    out[np.isnan(x)] = 0
    return out


def sofa_parts(cur: dict) -> dict:
    """Partial SOFA from current recorded values (no GCS, no vasopressors)."""
    plt_ = cur["Platelets"]
    with np.errstate(invalid="ignore"):
        coag = np.select([plt_ < 20, plt_ < 50, plt_ < 100, plt_ < 150], [4, 3, 2, 1], 0).astype(np.float32)
    liver = _points(cur["Bilirubin_total"], [1.2, 2.0, 6.0, 12.0], [1, 2, 3, 4])
    renal = _points(cur["Creatinine"], [1.2, 2.0, 3.5, 5.0], [1, 2, 3, 4])
    with np.errstate(invalid="ignore"):
        cardio = np.where(cur["MAP"] < 70, 1, 0).astype(np.float32)
        fio2 = np.where(cur["FiO2"] > 1, cur["FiO2"] / 100, cur["FiO2"])
        fio2 = np.where(np.isnan(fio2), 0.21, fio2)
        sf = cur["O2Sat"] / np.maximum(fio2, 0.21)
        resp = np.select([sf < 89, sf < 148, sf < 221, sf < 302], [4, 3, 2, 1], 0).astype(np.float32)
    resp[np.isnan(cur["O2Sat"])] = 0
    parts = {"sofa_coag": coag, "sofa_liver": liver, "sofa_renal": renal,
             "sofa_cardio": cardio, "sofa_resp": resp}
    parts["sofa_total"] = sum(parts.values()).astype(np.float32)
    return parts


def extra_base(base: dict, chunk_rows: int = 200_000) -> dict:
    """Causal arrays for the version 2 block, built in patient-aligned chunks."""
    n = base["n"]
    if n <= chunk_rows:
        return _extra_base(base)
    starts = np.flatnonzero(np.r_[True, base["grp"][1:] != base["grp"][:-1]])
    cuts, last = [0], 0
    for s0 in starts:
        if s0 - last >= chunk_rows:
            cuts.append(int(s0))
            last = s0
    cuts.append(n)
    parts = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        sub = {k: (v[a:b] if isinstance(v, np.ndarray) and len(v) == n else v) for k, v in base.items()}
        sub["n"] = b - a
        parts.append(_extra_base(sub))
    out = {}
    for k, v in parts[0].items():
        if isinstance(v, np.ndarray):
            out[k] = np.concatenate([p_[k] for p_ in parts])
        elif isinstance(v, dict):
            out[k] = {s_: np.concatenate([p_[k][s_] for p_ in parts]) for s_ in v}
        else:
            out[k] = v
    return out


def _extra_base(base: dict) -> dict:
    """Causal arrays for the version 2 block, from version 1's base."""
    var, grp = base["variables"], base["grp"]
    cur = {v: base["current"][:, var.index(v)] for v in var}
    # "real" readings this hour, for rolling windows
    obs = base["observed"]
    vitals = base["vitals"]
    vi = [var.index(v) for v in vitals]
    li = [var.index(v) for v in KEY_LABS if v in var]
    raw_v = np.where(obs[:, vi], base["current"][:, vi], np.nan).astype(np.float32)
    raw_l = np.where(obs[:, li], base["current"][:, li], np.nan).astype(np.float32)

    out = {}
    sv = _lag_stack(raw_v, grp, WIN)
    out["v24"] = {s: _nanstat(sv, f) for s, f in (("min", np.nanmin), ("max", np.nanmax), ("mean", np.nanmean))}
    del sv
    sl = _lag_stack(raw_l, grp, WIN)
    out["l24"] = {s: _nanstat(sl, f) for s, f in (("min", np.nanmin), ("max", np.nanmax))}
    del sl

    parts = sofa_parts(cur)
    out["sofa"] = parts
    st = _lag_stack(parts["sofa_total"][:, None], grp, WIN)[:, :, 0]
    out["sofa_rise"] = (parts["sofa_total"] - np.nanmin(st, axis=0)).astype(np.float32)
    del st

    # baseline: first recorded value of the stay, carried forward (causal)
    bi = [var.index(v) for v in BASELINE_VARS if v in var]
    first = np.full((base["n"], len(bi)), np.nan, np.float32)
    g = pd.Series(grp)
    for k, j in enumerate(bi):
        o = obs[:, j]
        n_seen = pd.Series(o.astype(np.int32)).groupby(g).cumsum().to_numpy()
        is_first = o & (n_seen == 1)          # the patient's first real reading
        v = np.where(is_first, base["current"][:, j], np.nan)
        first[:, k] = pd.Series(v).groupby(g).ffill().to_numpy()  # carried forward only
    cur_b = base["current"][:, bi]
    out["base_delta"] = (cur_b - first).astype(np.float32)
    out["base_vars"] = [var[j] for j in bi]
    out["v24_vars"], out["l24_vars"] = vitals, [var[j] for j in li]
    return out


def fit_pools_v2(xb: dict, train_mask: np.ndarray) -> dict:
    d = xb["base_delta"][train_mask]
    return {"base_delta": [np.sort(d[~np.isnan(d[:, k]), k]) for k in range(d.shape[1])]}


def extra_block(base: dict, xb: dict, pools2: dict, filled_current: pd.DataFrame) -> pd.DataFrame:
    """Version 2 columns. filled_current: version 1 values block (gap-filled)."""
    pid, hour = base["pid"], base["hour"]
    cols = {}
    for k, v in enumerate(xb["v24_vars"]):
        for s, arr in xb["v24"].items():
            c = arr[:, k].copy()
            m = np.isnan(c)
            c[m] = filled_current[v].to_numpy()[m]
            cols[f"{v}_{s}24"] = c
    for k, v in enumerate(xb["l24_vars"]):
        for s, arr in xb["l24"].items():
            c = arr[:, k].copy()
            m = np.isnan(c)
            c[m] = filled_current[v].to_numpy()[m]
            cols[f"{v}_{s}24"] = c
    for name, arr in xb["sofa"].items():
        cols[name] = arr
    cols["sofa_rise24"] = xb["sofa_rise"]
    for k, v in enumerate(xb["base_vars"]):
        cols[f"{v}_from_baseline"] = _fill(xb["base_delta"][:, k], pools2["base_delta"][k], pid, hour, 4000 + k)
    return pd.DataFrame(cols).astype(np.float32)
