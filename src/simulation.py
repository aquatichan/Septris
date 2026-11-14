"""Full-cohort review-slot sweep (v3 brief).

Every test patient of the target hospital passes through a 20-bed unit
exactly once, in a shuffled admission order. Each 12-hour shift has k
evenly spaced review slots; at each slot a policy picks one patient in a
bed who was not reviewed in the last 12 hours. The bed schedule depends only
on the admission order, so every policy faces the same patients at the same
moments.
"""

from __future__ import annotations

import heapq
import zlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import BEDS, SHIFT_HOURS, SNOOZE_HOURS
from .labels import ELIGIBLE, UNCERTAIN

EARLY, EARLY6, LATE, FALSE, UNCERT = "early", "early6", "late", "false", "uncertain"


def slot_hours(k: int, shift: int = SHIFT_HOURS) -> list[int]:
    """k evenly spaced slot offsets within a shift, rounded down."""
    return sorted({int(np.floor(i * shift / k)) for i in range(k)})


@dataclass
class Cohort:
    """Test patients of one hospital with per-hour scores per policy."""
    n_hours: np.ndarray          # record length per patient
    t_onset: np.ndarray          # NaN for non-septic
    group: np.ndarray            # eligibility group per patient
    offsets: np.ndarray          # start row of each patient in score arrays
    scores: dict                 # policy -> float array over all rows


def classify(t_onset: np.ndarray, group: np.ndarray, rev_p, rev_h) -> np.ndarray:
    """Class of every review: early6, early, late, false or uncertain."""
    out = np.empty(len(rev_p), object)
    lead = t_onset[rev_p] - rev_h
    g = group[rev_p]
    elig = g == ELIGIBLE
    out[:] = FALSE
    out[g == UNCERTAIN] = UNCERT
    out[elig & (lead <= 0)] = LATE
    out[elig & (lead > 0) & (lead <= 12)] = EARLY
    out[elig & (lead >= 6) & (lead <= 12)] = EARLY6
    return out


def summarize_run(cohort: Cohort, run_patients: np.ndarray, rev_pos: np.ndarray,
                  rev_h: np.ndarray, end: int, denom_mask: np.ndarray | None = None) -> dict:
    """Patient-level metrics for one simulated run.

    run_patients: cohort index for each queue position (duplicates allowed).
    rev_pos: queue position of each reviewed patient (unique identity under
    bootstrap). denom_mask: boolean over queue positions limiting which
    patients count (for subgroups).
    """
    pat = run_patients[rev_pos]
    cls = classify(cohort.t_onset, cohort.group, pat, rev_h)
    lead = cohort.t_onset[pat] - rev_h
    n_pos = len(run_patients)
    elig = cohort.group[run_patients] == ELIGIBLE
    if denom_mask is not None:
        elig = elig & denom_mask
    first_early_lead = np.full(n_pos, np.nan)
    caught3 = np.zeros(n_pos, bool)
    caught6 = np.zeros(n_pos, bool)
    early_idx = np.flatnonzero((cls == EARLY) | (cls == EARLY6))
    for i in early_idx:
        q = rev_pos[i]
        if np.isnan(first_early_lead[q]):
            first_early_lead[q] = lead[i]
        if lead[i] >= 3:
            caught3[q] = True
        if cls[i] == EARLY6:
            caught6[q] = True
    caught = ~np.isnan(first_early_lead)
    E = int(elig.sum())
    shifts = max(1, int(np.ceil(end / SHIFT_HOURS)))
    in_denom_rev = np.ones(len(rev_pos), bool) if denom_mask is None else denom_mask[rev_pos]
    n_early = int(np.isin(cls[in_denom_rev], [EARLY, EARLY6]).sum())
    n_false = int((cls[in_denom_rev] == FALSE).sum())
    n_late = int((cls[in_denom_rev] == LATE).sum())
    n_unc = int((cls[in_denom_rev] == UNCERT).sum())
    leads = first_early_lead[caught & elig]
    return {
        "eligible": E,
        "caught6_n": int((caught6 & elig).sum()),
        "caught6": (caught6 & elig).sum() / E if E else np.nan,
        "caught_any": (caught & elig).sum() / E if E else np.nan,
        "caught3": (caught3 & elig).sum() / E if E else np.nan,
        "missed_n": int((~caught & elig).sum()),
        "missed": (~caught & elig).sum() / E if E else np.nan,
        "median_lead": float(np.median(leads)) if len(leads) else np.nan,
        "false_per_shift": n_false / shifts,
        "late_per_shift": n_late / shifts,
        "uncertain_reviews": n_unc,
        "precision": n_early / max(1, n_early + n_false + n_late),
        "reviews": len(rev_pos),
        "shifts": shifts,
    }


def sweep(cohort: Cohort, policies: list[str], k: int, seed: int,
          resample: np.ndarray | None = None, denom_masks: dict | None = None):
    """One admission order; every policy on the same bed schedule.

    resample: optional cohort indices (bootstrap) to use instead of all
    patients. Returns {policy: metrics} and, for each policy, the review log.
    """
    rng = np.random.default_rng(seed)
    base = np.arange(len(cohort.n_hours)) if resample is None else resample
    order_pos = rng.permutation(len(base))
    run_patients = base[order_pos]            # cohort index per queue position
    nh = cohort.n_hours
    # schedule over queue positions
    free = [(0, b) for b in range(BEDS)]
    heapq.heapify(free)
    admit = np.empty(len(run_patients), np.int64)
    bed = np.empty(len(run_patients), np.int64)
    for i, p in enumerate(run_patients):
        t, b = heapq.heappop(free)
        admit[i], bed[i] = t, b
        heapq.heappush(free, (t + int(nh[p]), b))
    end = int(max(t for t, _ in free))
    stops = admit + nh[run_patients]
    # occupancy by hour (queue positions)
    occ_hours = np.concatenate([np.arange(a, s) for a, s in zip(admit, stops)])
    occ_pos = np.repeat(np.arange(len(run_patients)), nh[run_patients])
    srt = np.argsort(occ_hours, kind="stable")
    occ_hours, occ_pos = occ_hours[srt], occ_pos[srt]
    bounds = np.searchsorted(occ_hours, np.arange(end + 1))
    beds_used = np.diff(bounds)
    offs = slot_hours(k)
    slot_times = np.array([t for t in range(end) if t % SHIFT_HOURS in offs])
    under = float(np.mean([beds_used[s:s + SHIFT_HOURS].min() < BEDS
                           for s in range(0, end, SHIFT_HOURS)]))

    out, logs = {}, {}
    for pol in policies:
        prng = np.random.default_rng([seed, zlib.crc32(pol.encode())])
        last = np.full(len(run_patients), -10_000, np.int64)
        rev_pos, rev_h = [], []
        sc = cohort.scores.get(pol)
        for t in slot_times:
            occ = occ_pos[bounds[t]:bounds[t + 1]]
            if len(occ) == 0:
                continue
            ok = occ[last[occ] <= t - SNOOZE_HOURS]
            if len(ok) == 0:
                continue
            rh = t - admit[ok]
            if pol == "random":
                j = int(prng.integers(len(ok)))
            else:
                s = sc[cohort.offsets[run_patients[ok]] + rh]
                best = np.flatnonzero(s == s.max())
                j = int(best[prng.integers(len(best))]) if len(best) > 1 else int(best[0])
            last[ok[j]] = t
            rev_pos.append(int(ok[j]))
            rev_h.append(int(rh[j]))
        rev_pos = np.asarray(rev_pos, np.int64)
        rev_h = np.asarray(rev_h, np.int64)
        m = summarize_run(cohort, run_patients, rev_pos, rev_h, end)
        m["shifts_under_20_beds"] = under
        out[pol] = m
        if denom_masks:
            for name, mask in denom_masks.items():
                sm = summarize_run(cohort, run_patients, rev_pos, rev_h, end,
                                   denom_mask=mask[run_patients])
                out[f"{pol}|{name}"] = sm
        logs[pol] = pd.DataFrame({
            "queue_pos": rev_pos, "cohort_idx": run_patients[rev_pos],
            "record_hour": rev_h, "unit_hour": admit[rev_pos] + rev_h,
        })
    return out, logs, {"run_patients": run_patients, "admit": admit, "bed": bed, "end": end}
