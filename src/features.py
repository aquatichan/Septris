"""Leakage-safe hourly features: values-only, missingness-only, combined.

Every feature at hour h uses only rows up to and including h of the same
patient (ffill and backward shifts within the patient). Gaps in the
values-only set are filled with a draw from the training hospital's real
values; the draw index is a hash of (patient, hour, variable), so it is
identical whether the record is read in full or cut off at h. No NaN is
passed to any model.

Usage:
    base = causal_base(df, variables)        # once per data table
    pools = fit_pools(base, train_mask)       # once per training hospital
    X = assemble(base, pools, feature_set)    # "values", "missing", "combined"
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from .config import LAB_STALE_HOURS, ROLL_HOURS, VITAL_STALE_HOURS
from .data_io import LABS, SHORTCUTS, VITALS

NEVER = 999.0  # "hours since last measurement" before any measurement


def _pid_int(s: pd.Series) -> np.ndarray:
    return s.str[1:].astype(np.int64).to_numpy()


def causal_base(df: pd.DataFrame, variables: list[str]) -> dict:
    """Per-row causal arrays shared by all feature sets.

    df must be sorted by patient_id then hour, with consecutive hours.
    Returns a dict of numpy arrays plus metadata.
    """
    df = df.reset_index(drop=True)
    pid = _pid_int(df["patient_id"])
    hour = df["hour"].to_numpy(np.int64)
    new_pt = np.r_[True, pid[1:] != pid[:-1]]
    grp = np.cumsum(new_pt) - 1
    g = pd.Series(grp)

    vitals = [v for v in variables if v in VITALS]
    labs = [v for v in variables if v in LABS]
    raw = df[variables].to_numpy(np.float64)
    observed = ~np.isnan(raw)

    raw_df = pd.DataFrame(raw, columns=variables)
    last_val = raw_df.groupby(grp).ffill().to_numpy()
    obs_hour = pd.DataFrame(np.where(observed, hour[:, None], np.nan), columns=variables)
    last_hour = obs_hour.groupby(grp).ffill().to_numpy()
    since = np.where(np.isnan(last_hour), NEVER, hour[:, None] - last_hour)

    # previous real measurement (the one before the most recent)
    prev_val = np.full_like(raw, np.nan)
    for j, v in enumerate(variables):
        o = observed[:, j]
        idx = np.flatnonzero(o)
        if len(idx) == 0:
            continue
        vals, gg = raw[idx, j], grp[idx]
        shifted = np.r_[np.nan, vals[:-1]]
        shifted[np.r_[True, gg[1:] != gg[:-1]]] = np.nan
        col = np.full(len(raw), np.nan)
        col[idx] = shifted
        prev_val[:, j] = pd.Series(col).groupby(grp).ffill().to_numpy()

    stale = np.array([VITAL_STALE_HOURS if v in VITALS else LAB_STALE_HOURS for v in variables])
    current = np.where(since <= stale[None, :], last_val, np.nan)
    delta = np.where(np.isnan(current), np.nan, last_val - prev_val)

    # rolling window over real vital measurements in hours h-5..h
    vi = [variables.index(v) for v in vitals]
    roll = {}
    stack = np.full((ROLL_HOURS, len(raw), len(vi)), np.nan)
    for lag in range(ROLL_HOURS):
        sh = np.full((len(raw), len(vi)), np.nan)
        if lag == 0:
            sh[:] = raw[:, vi]
        else:
            sh[lag:] = raw[:-lag, vi]
            same = np.zeros(len(raw), bool)
            same[lag:] = grp[lag:] == grp[:-lag]
            sh[~same] = np.nan
        stack[lag] = sh
    with warnings.catch_warnings():  # all-NaN windows are expected
        warnings.simplefilter("ignore", RuntimeWarning)
        roll["min"] = np.nanmin(stack, axis=0)
        roll["max"] = np.nanmax(stack, axis=0)
        roll["mean"] = np.nanmean(stack, axis=0)
    del stack

    return {
        "pid": pid, "hour": hour, "grp": grp, "variables": variables,
        "vitals": vitals, "labs": labs, "observed": observed, "since": since,
        "current": current, "delta": delta, "roll": roll,
        "age": df["Age"].to_numpy(np.float64),
        "gender": df["Gender"].to_numpy(np.float64),
        "shortcuts": df[SHORTCUTS].to_numpy(np.float64),
        "n": len(df),
    }


def fit_pools(base: dict, train_mask: np.ndarray) -> dict:
    """Real observed values from training rows, used to fill gaps."""
    pools = {"current": [], "delta": [], "roll": []}
    for j in range(len(base["variables"])):
        col = base["current"][train_mask, j]
        pools["current"].append(np.sort(col[~np.isnan(col)]))
        d = base["delta"][train_mask, j]
        pools["delta"].append(np.sort(d[~np.isnan(d)]))
    for k in range(len(base["vitals"])):
        col = base["roll"]["mean"][train_mask, k]
        pools["roll"].append(np.sort(col[~np.isnan(col)]))
    a = base["age"][train_mask]
    pools["age"] = np.sort(a[~np.isnan(a)])
    return pools


def _hash_index(pid: np.ndarray, hour: np.ndarray, salt: int, n: int) -> np.ndarray:
    """Deterministic pseudo-random index in [0, n) from (patient, hour, salt)."""
    with np.errstate(over="ignore"):  # wraparound is intended
        x = (pid.astype(np.uint64) * np.uint64(0x9E3779B97F4A7C15)
             + hour.astype(np.uint64) * np.uint64(0xBF58476D1CE4E5B9)
             + np.full(pid.shape, salt, np.uint64) * np.uint64(0x94D049BB133111EB))
        x ^= x >> np.uint64(31)
        x *= np.uint64(0xD6E8FEB86659FD93)
        x ^= x >> np.uint64(29)
    return (x % np.uint64(max(n, 1))).astype(np.int64)


def _fill(col: np.ndarray, pool: np.ndarray, pid, hour, salt) -> np.ndarray:
    out = col.copy()
    miss = np.isnan(out)
    if miss.any():
        if len(pool) == 0:
            out[miss] = 0.0
        else:
            out[miss] = pool[_hash_index(pid[miss], hour[miss], salt, len(pool))]
    return out


def values_block(base: dict, pools: dict) -> pd.DataFrame:
    pid, hour = base["pid"], base["hour"]
    cols = {}
    variables = base["variables"]
    for j, v in enumerate(variables):
        cols[v] = _fill(base["current"][:, j], pools["current"][j], pid, hour, 1000 + j)
    for j, v in enumerate(variables):
        if v in base["vitals"]:
            cols[f"{v}_delta"] = _fill(base["delta"][:, j], pools["delta"][j], pid, hour, 2000 + j)
    for k, v in enumerate(base["vitals"]):
        j = variables.index(v)
        for stat in ("min", "max", "mean"):
            col = base["roll"][stat][:, k].copy()
            miss = np.isnan(col)
            col[miss] = cols[v][miss]  # no real reading in window: use the filled current value
            cols[f"{v}_{stat}6"] = col
    if "HR" in cols and "SBP" in cols:
        cols["shock_index"] = cols["HR"] / np.maximum(cols["SBP"], 1.0)
    cols["age"] = _fill(base["age"], pools["age"], pid, hour, 3000)
    cols["sex"] = np.nan_to_num(base["gender"], nan=0.0)
    return pd.DataFrame(cols).astype(np.float32)


def missing_block(base: dict) -> pd.DataFrame:
    cols = {}
    since = base["since"]
    for j, v in enumerate(base["variables"]):
        cols[f"m_{v}_now"] = base["observed"][:, j].astype(np.float32)
        cols[f"m_{v}_6h"] = (since[:, j] < 6).astype(np.float32)
        cols[f"m_{v}_24h"] = (since[:, j] < 24).astype(np.float32)
        cols[f"m_{v}_since"] = np.minimum(since[:, j], NEVER).astype(np.float32)
    lab_idx = [base["variables"].index(v) for v in base["labs"]]
    cols["m_labs_24h"] = (since[:, lab_idx] < 24).sum(axis=1).astype(np.float32)
    return pd.DataFrame(cols)


def shortcut_block(base: dict) -> pd.DataFrame:
    return pd.DataFrame(np.nan_to_num(base["shortcuts"], nan=-1.0),
                        columns=SHORTCUTS).astype(np.float32)


def assemble(base: dict, pools: dict | None, feature_set: str) -> pd.DataFrame:
    if feature_set == "values":
        return values_block(base, pools)
    if feature_set == "missing":
        return missing_block(base)
    if feature_set == "combined":
        return pd.concat([values_block(base, pools), missing_block(base)], axis=1)
    if feature_set == "shortcuts":
        return pd.concat([values_block(base, pools), missing_block(base),
                          shortcut_block(base)], axis=1)
    raise ValueError(feature_set)


def current_values(base: dict, pools: dict) -> pd.DataFrame:
    """Current carried-forward values only (logistic regression input)."""
    v = values_block(base, pools)
    keep = list(base["variables"]) + ["age", "sex"]
    return v[keep]


def sirs_count(base: dict) -> np.ndarray:
    """SIRS criteria on current carried values; missing scores 0."""
    var = base["variables"]
    cur = base["current"]

    def c(name):
        return cur[:, var.index(name)] if name in var else np.full(base["n"], np.nan)

    with np.errstate(invalid="ignore"):
        t, hr, rr, pa, wbc = c("Temp"), c("HR"), c("Resp"), c("PaCO2"), c("WBC")
        pts = ((t > 38) | (t < 36)).astype(int)
        pts += (hr > 90).astype(int)
        pts += ((rr > 20) | (pa < 32)).astype(int)
        pts += ((wbc > 12) | (wbc < 4)).astype(int)
    return pts


def news_score(base: dict) -> np.ndarray:
    """NEWS-inspired score on current values; missing scores 0, no consciousness."""
    var = base["variables"]
    cur = base["current"]

    def c(name):
        return cur[:, var.index(name)] if name in var else np.full(base["n"], np.nan)

    rr, spo2, sbp, hr, t, fio2 = c("Resp"), c("O2Sat"), c("SBP"), c("HR"), c("Temp"), c("FiO2")
    s = np.zeros(base["n"])
    with np.errstate(invalid="ignore"):
        s += np.select([rr <= 8, rr <= 11, rr <= 20, rr <= 24, rr >= 25], [3, 1, 0, 2, 3], 0)
        s += np.select([spo2 <= 91, spo2 <= 93, spo2 <= 95, spo2 >= 96], [3, 2, 1, 0], 0)
        s += np.select([sbp <= 90, sbp <= 100, sbp <= 110, sbp <= 219, sbp >= 220], [3, 2, 1, 0, 3], 0)
        s += np.select([hr <= 40, hr <= 50, hr <= 90, hr <= 110, hr <= 130, hr >= 131], [3, 1, 0, 1, 2, 3], 0)
        s += np.select([t <= 35.0, t <= 36.0, t <= 38.0, t <= 39.0, t >= 39.1], [3, 1, 0, 1, 2], 0)
        s += np.where(fio2 > 0.21, 2, 0)
    return s
