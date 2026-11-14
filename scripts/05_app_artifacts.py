"""Step 5: precompute everything the Gradio app shows (run after 04).

The app never trains, downloads or scores anything; it only reads
app/artifacts/. The demo replays Hospital A test patients through the
20-bed unit with 5 reviews per 12-hour shift (admission order seed 1).
Septris (A-trained LightGBM, combined features) and random review face
the same beds at the same moments, so the app can show both side by side.

Artifacts:
  slots.parquet      one row per review: clock time, bed, pick, reasons,
                     hindsight verdict, what random review would have opened,
                     running scoreboard
  beds.parquet       the 20 beds at every review (rank, tier, snooze, hindsight)
  timelines.parquet  hourly risk percentile and a few vitals per patient
  reviews.parquet    every Septris review per patient
  patients.parquet   onset hour and basics per patient
  examples.json      review indices for good catches, misses and false alarms
  demo.json          the run's settings and totals
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lightgbm as lgb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import config as C, explanations as E, features as F, simulation as S  # noqa: E402
from src.labels import ELIGIBLE  # noqa: E402

RES = ROOT / "outputs/results"
ART = ROOT / "app/artifacts"
SEL = ROOT / "outputs/blend_selection.json"
DEPLOY = "blend" if SEL.exists() else "lgbm_combined"
POLICY = f"A:{DEPLOY}"
K_DEMO = 5
SEED_DEMO = 1
START_CLOCK = 7  # unit hour 0 is 7:00 AM on day 1; shifts run 7 AM-7 PM and 7 PM-7 AM


def clock(t: int) -> tuple[int, str, str]:
    day = t // 24 + 1
    h = (START_CLOCK + t) % 24
    label = f"{(h % 12) or 12}:00 {'AM' if h < 12 else 'PM'}"
    shift = "Day shift" if 7 <= h < 19 else "Night shift"
    return day, label, shift


def verdict(cls: str, lead: float, group: str) -> tuple[str, str]:
    """(short label, one plain sentence) for a review, known only in hindsight."""
    if cls == S.EARLY6:
        return "Good catch", (f"This patient's sepsis was recorded {lead:.0f} hours after this check, "
                              "so the nurse would have had a 6–12 hour head start.")
    if cls == S.EARLY:
        return "Caught, but close", (f"Sepsis was recorded {lead:.0f} hour{'s' if lead != 1 else ''} after "
                                     "this check: early, but less than the 6-hour head start we aim for.")
    if cls == S.LATE:
        ago = -lead
        when = "in this same hour" if ago == 0 else f"{ago:.0f} hour{'s' if ago != 1 else ''} before this check"
        return "Too late", f"Sepsis had already been recorded {when}."
    if cls == S.UNCERT:
        return "Not counted", "This patient was already labelled septic on arrival, so the check counts neither way."
    if group == ELIGIBLE and lead > 12:
        return "False alarm", (f"Sepsis was not recorded until {lead:.0f} hours later, outside the 12-hour "
                               "window, so this check counts as a false alarm.")
    return "False alarm", "This patient did not develop sepsis in the next 12 hours."


def comparison_html(deploy):
    """Plain sentences on where LightGBM, the GRU and the mix win (from 03's results)."""
    t = pd.read_csv(RES / "results_table.csv")
    t = t[t.subgroup == "all"]
    if "A:temporal_gru" not in set(t.policy):
        return "<p>The GRU comparison has not been run.</p>"

    def v(T, H, m, k):
        r = t[(t.test == T) & (t.k == k) & (t.policy == f"{H}:{m}")]
        return 100 * float(r.caught6.iloc[0]) if len(r) else float("nan")

    rows = ""
    for k in (3, 5):
        for T in C.HOSPITALS:
            for H in (T, "B" if T == "A" else "A"):
                cells = [v(T, H, m, k) for m in ("lgbm_combined", "temporal_gru", deploy)]
                best = max(cells[:2])
                fmt = [f"<b>{c:.1f}</b>" if c == best and i < 2 else f"{c:.1f}" for i, c in enumerate(cells)]
                where = "trained there" if H == T else f"trained at {H} (never saw {T})"
                rows += (f"<tr><td>{k}</td><td>Hospital {T}, {where}</td><td>{fmt[0]}</td><td>{fmt[1]}</td>"
                         f"<td style='color:#1d4ed8'><b>{cells[2]:.1f}</b></td></tr>")
    return ("<p><b>LightGBM vs Miheer's GRU vs the Septris mix</b>, caught in time out of 100 sepsis patients "
            "(bold = the better of the two single models):</p>"
            "<table style='width:100%; border-collapse:collapse; font-size:15px'>"
            "<tr style='text-align:left; border-bottom:1px solid #d0d5dd'><th>Reviews per shift</th><th>Tested on</th>"
            "<th>LightGBM</th><th>GRU</th><th>Septris mix</th></tr>" + rows + "</table>")


def main():
    ART.mkdir(parents=True, exist_ok=True)
    rows = pd.read_parquet(ROOT / "data/processed/rows.parquet")
    hourly = pd.read_parquet(ROOT / "data/processed/hourly.parquet").sort_values(
        ["patient_id", "hour"], kind="stable").reset_index(drop=True)
    patients = pd.read_csv(ROOT / "outputs/patients.csv").set_index("patient_id")
    variables = json.loads((ROOT / "outputs/variables_used.json").read_text())["used"]
    score = np.load(ROOT / f"data/processed/scores/A_{DEPLOY}.npy")
    hosp, split = rows["hospital"].to_numpy(), rows["split"].to_numpy()

    # priority tiers and percentiles from home validation scores (fixed before test)
    va = (hosp == "A") & (split == "val")
    val_sorted = np.sort(score[va])
    hi_cut, med_cut = np.quantile(score[va], [0.95, 0.80])

    def pct(s):
        return 100.0 * np.searchsorted(val_sorted, s, side="right") / len(val_sorted)

    def tier(s):
        return "High" if s >= hi_cut else "Medium" if s >= med_cut else "Low"

    te = (hosp == "A") & (split == "test")
    r = rows[te].reset_index(drop=True)
    ids = r["patient_id"].drop_duplicates().to_numpy()
    n_hours = r.groupby("patient_id", sort=False).size().loc[ids].to_numpy()
    offsets = np.r_[0, np.cumsum(n_hours)[:-1]]
    s_te = score[te]
    p = patients.loc[ids]
    t_onset = p["t_onset"].to_numpy(float)
    group = p["group"].to_numpy(object)
    cohort = S.Cohort(n_hours=n_hours, t_onset=t_onset, group=group, offsets=offsets,
                      scores={POLICY: s_te})

    out, logs, info = S.sweep(cohort, [POLICY, "random"], K_DEMO, SEED_DEMO)
    run_patients, admit, bedno, end = info["run_patients"], info["admit"], info["bed"], info["end"]
    stops = admit + n_hours[run_patients]
    sb, rnd = logs[POLICY], logs["random"]
    sb_at = dict(zip(sb["unit_hour"], sb["queue_pos"]))
    rnd_at = dict(zip(rnd["unit_hour"], rnd["queue_pos"]))
    sb_reviews = sb.groupby("queue_pos")["unit_hour"].apply(list).to_dict()
    offs = S.slot_hours(K_DEMO)

    # why-now reasons for every Septris pick
    tr = (hosp == "A") & (split == "train") & rows["in_training"].to_numpy()
    base = F.causal_base(hourly, variables)
    pools = F.fit_pools(base, tr)
    X = F.assemble(base, pools, "combined")
    model = lgb.Booster(model_file=str(ROOT / "outputs/models/A_lgbm_combined.txt"))
    test_rows = np.flatnonzero(te)
    sb_sorted = sb.sort_values("unit_hour").reset_index(drop=True)
    pick_rows = test_rows[offsets[sb_sorted["cohort_idx"].to_numpy()] + sb_sorted["record_hour"].to_numpy()]
    contrib = model.predict(X.iloc[pick_rows], pred_contrib=True)
    cols = list(X.columns)
    reasons = {int(u): E.reasons(X.iloc[row], contrib[i, :-1], cols, base, int(row))
               for i, (u, row) in enumerate(zip(sb_sorted["unit_hour"], pick_rows))}
    del X, base

    def judge(q, t):
        ci = int(run_patients[q])
        rh = int(t - admit[q])
        cls = S.classify(t_onset, group, np.array([ci]), np.array([rh]))[0]
        lead = t_onset[ci] - rh
        return ci, rh, cls, lead

    onset_unit = admit + np.where(np.isnan(t_onset[run_patients]), np.inf, t_onset[run_patients])
    eligible_pos = group[run_patients] == ELIGIBLE
    caught = {POLICY: np.zeros(len(run_patients), bool), "random": np.zeros(len(run_patients), bool)}

    slot_records, bed_records = [], []
    for t in sorted(set(sb["unit_hour"]) | set(rnd["unit_hour"])):
        q = sb_at.get(t)
        if q is None:
            continue
        ci, rh, cls, lead = judge(q, t)
        if cls == S.EARLY6:
            caught[POLICY][q] = True
        qr = rnd_at.get(t)
        r_cls, r_bed = None, None
        if qr is not None:
            _, _, r_cls, r_lead = judge(qr, t)
            r_bed = int(bedno[qr]) + 1
            if r_cls == S.EARLY6:
                caught["random"][qr] = True
        day, label, shift_name = clock(t)
        shift, offset = divmod(t, C.SHIFT_HOURS)
        onset_passed = eligible_pos & (onset_unit <= t)
        short, sentence = verdict(cls, lead, group[ci])
        r_short = verdict(r_cls, r_lead, group[int(run_patients[qr])])[0] if qr is not None else None
        slot_records.append({
            "unit_hour": int(t), "day": day, "clock": label, "shift_name": shift_name,
            "shift": int(shift) + 1, "check": offs.index(offset) + 1,
            "bed": int(bedno[q]) + 1, "patient_id": ids[ci], "record_hour": rh,
            "reasons": " | ".join(reasons.get(int(t), [])),
            "review_class": cls, "lead_hours": lead, "verdict": short, "verdict_text": sentence,
            "random_bed": r_bed, "random_class": r_cls, "random_verdict": r_short,
            "sepsis_so_far": int(onset_passed.sum()),
            "sb_caught_so_far": int((caught[POLICY] & onset_passed).sum()),
            "random_caught_so_far": int((caught["random"] & onset_passed).sum()),
        })
        # the 20 beds at this moment
        occ = np.flatnonzero((admit <= t) & (stops > t))
        cand = []
        for qq in occ:
            cj = int(run_patients[qq])
            rr = int(t - admit[qq])
            sc = float(s_te[offsets[cj] + rr])
            last = [u for u in sb_reviews.get(qq, []) if u < t]
            snoozed = bool(last) and t - last[-1] < C.SNOOZE_HOURS
            to_onset = t_onset[cj] - rr if group[cj] == ELIGIBLE else np.nan
            cand.append({"unit_hour": int(t), "bed": int(bedno[qq]) + 1, "patient_id": ids[cj],
                         "hours_in_icu": rr + 1, "record_hour": rr, "score": sc,
                         "percentile": float(pct(sc)), "tier": tier(sc),
                         "snoozed": snoozed, "hours_since_check": (t - last[-1]) if last else -1,
                         "picked": bool(qq == q), "random_pick": bool(qq == qr),
                         "hours_to_sepsis": to_onset})
        ok = sorted((c for c in cand if not c["snoozed"]), key=lambda c: -c["score"])
        for rank, c in enumerate(ok, 1):
            c["rank"] = rank
        for c in cand:
            c.setdefault("rank", 0)
            c["candidates"] = len(ok)
        bed_records.extend(cand)

    slots_df = pd.DataFrame(slot_records)
    beds_df = pd.DataFrame(bed_records)
    slots_df.to_parquet(ART / "slots.parquet", index=False)
    beds_df.to_parquet(ART / "beds.parquet", index=False)

    # example finder: good catches, false alarms and misses (septic, never caught 6-12 h early)
    idx_of = {u: i for i, u in enumerate(slots_df["unit_hour"])}
    full = beds_df.groupby("unit_hour").size()
    busy = set(full.index[full >= C.BEDS])
    good = [i for i, (u, c) in enumerate(zip(slots_df["unit_hour"], slots_df["review_class"]))
            if c == S.EARLY6 and u in busy]
    false = [i for i, (u, c) in enumerate(zip(slots_df["unit_hour"], slots_df["review_class"]))
             if c == S.FALSE and u in busy]
    misses = []
    for qq in np.flatnonzero(eligible_pos & ~caught[POLICY]):
        cj = int(run_patients[qq])
        target = admit[qq] + t_onset[cj] - 9
        win = beds_df[(beds_df["patient_id"] == ids[cj]) & (beds_df["hours_to_sepsis"] >= 6)
                      & (beds_df["hours_to_sepsis"] <= 12)]
        if win.empty:
            continue
        u = int(win.loc[(win["unit_hour"] - target).abs().idxmin(), "unit_hour"])
        if u in busy:
            misses.append({"slot": idx_of[u], "bed": int(bedno[qq]) + 1, "patient_id": ids[cj]})
    misses.sort(key=lambda m: m["slot"])
    rng = np.random.default_rng(C.SEED)
    pick = lambda xs, n=40: sorted(rng.choice(xs, size=min(n, len(xs)), replace=False).tolist(),  # noqa: E731
                                   key=lambda x: x["slot"] if isinstance(x, dict) else x)
    examples = {"good": [int(i) for i in pick(good)], "false": [int(i) for i in pick(false)],
                "miss": pick(misses)}
    (ART / "examples.json").write_text(json.dumps(examples, indent=1))

    # timelines for every A test patient (only fields the app plots)
    h = hourly.loc[te, ["patient_id", "hour", "HR", "MAP", "Resp", "Temp", "Lactate", "WBC"]].copy()
    h["percentile"] = pct(s_te).astype("float32")
    h.to_parquet(ART / "timelines.parquet", index=False)
    rev = [{"patient_id": ids[int(run_patients[qq])], "record_hour": int(u - admit[qq])}
           for qq, times in sb_reviews.items() for u in times]
    pd.DataFrame(rev).to_parquet(ART / "reviews.parquet", index=False)
    meta = patients.loc[ids, ["t_onset", "group", "age", "gender", "n_hours"]].reset_index()
    meta.to_parquet(ART / "patients.parquet", index=False)

    # results tables for the Results tab
    for f in ("results_table.csv", "paired_differences.csv", "hourly_metrics.csv",
              "before_new_testing.csv", "utility_scores.csv", "null_check.json"):
        src = RES / f
        if src.exists():
            (ART / f).write_bytes(src.read_bytes())
    (ART / "failure_cases.json").unlink(missing_ok=True)
    (ART / "tiers.json").write_text(json.dumps({"high": float(hi_cut), "medium": float(med_cut)}))
    if DEPLOY == "blend":
        w = json.loads(SEL.read_text())["lightgbm_weight"]
        label = ("LightGBM alone" if w == 1 else "GRU alone" if w == 0 else
                 f"mix: {100 * w:.0f}% LightGBM + {100 * (1 - w):.0f}% GRU")
        model_text = (f"Two models, mixed {100 * w:.0f}/{100 * (1 - w):.0f}. LightGBM (a gradient-boosted decision-tree "
                      "model) reads hand-made summaries of each patient's last few hours: current values, recent "
                      "changes, 6-hour highs and lows, and which tests were done when. A GRU (a deep-learning model "
                      "that reads each patient's hours in order, built by Miheer) reads the raw hour-by-hour values "
                      "and which ones were measured. Each model's score is turned into a 0-100 ranking and the two "
                      "rankings are averaged with these weights, which were chosen on validation patients only. "
                      "The 'what stood out' reasons come from the LightGBM part.")
    else:
        w, label = 1.0, "LightGBM"
        model_text = "A LightGBM model reading summaries of each patient's last few hours."
    demo = {"policy_key": DEPLOY, "policy_label": label, "lightgbm_weight": w, "model_text": model_text,
            "comparison_html": comparison_html(DEPLOY),
            "k": K_DEMO, "seed": SEED_DEMO, "beds": C.BEDS, "patients": int(len(ids)),
            "eligible_septic": int(eligible_pos.sum()), "days": round(end / 24, 1),
            "reviews": int(len(slots_df)),
            "sb_caught6": int(caught[POLICY][eligible_pos].sum()),
            "random_caught6": int(caught["random"][eligible_pos].sum()),
            "sb_false": int((slots_df["review_class"] == S.FALSE).sum()),
            "random_false": int((slots_df["random_class"] == S.FALSE).sum())}
    (ART / "demo.json").write_text(json.dumps(demo, indent=1))
    print(json.dumps(demo))
    print({k: len(v) for k, v in examples.items()})


if __name__ == "__main__":
    main()
