"""Step 5: precompute everything the Gradio app shows (run after 04).

The app never trains, downloads or scores anything; it only reads
app/artifacts/. Artifacts cover the A->A, k=3, seed-1 sweep of LightGBM
combined: every review slot, the 20 beds at that moment, the pick and its
"why now" reasons from LightGBM feature contributions, plus timelines.
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
POLICY = "A:lgbm_combined"


def main():
    ART.mkdir(parents=True, exist_ok=True)
    rows = pd.read_parquet(ROOT / "data/processed/rows.parquet")
    hourly = pd.read_parquet(ROOT / "data/processed/hourly.parquet").sort_values(
        ["patient_id", "hour"], kind="stable").reset_index(drop=True)
    patients = pd.read_csv(ROOT / "outputs/patients.csv").set_index("patient_id")
    variables = json.loads((ROOT / "outputs/variables_used.json").read_text())["used"]
    score = np.load(ROOT / "data/processed/scores/A_lgbm_combined.npy")
    hosp, split = rows["hospital"].to_numpy(), rows["split"].to_numpy()

    # priority tiers from home validation scores (fixed before looking at test)
    va = (hosp == "A") & (split == "val")
    hi_cut, med_cut = np.quantile(score[va], [0.95, 0.80])

    te = (hosp == "A") & (split == "test")
    r = rows[te].reset_index(drop=True)
    ids = r["patient_id"].drop_duplicates().to_numpy()
    n_hours = r.groupby("patient_id", sort=False).size().loc[ids].to_numpy()
    offsets = np.r_[0, np.cumsum(n_hours)[:-1]]
    s_te = score[te]

    pk = pd.read_pickle(RES / "review_logs_A.pkl")
    info, logd = pk["info"], pk["logs"][POLICY]
    run_patients, admit, end = info["run_patients"], info["admit"], info["end"]
    stops = admit + n_hours[run_patients]
    slots = sorted(set(t for t in range(end) if t % C.SHIFT_HOURS in S.slot_hours(C.PRIMARY_K)))
    pick_at = dict(zip(logd["unit_hour"], logd["queue_pos"]))
    reviews_by_pos = logd.groupby("queue_pos")["unit_hour"].apply(list).to_dict()

    # features + contributions only for picked rows (test A, model A)
    tr = (hosp == "A") & (split == "train") & rows["in_training"].to_numpy()
    base = F.causal_base(hourly, variables)
    pools = F.fit_pools(base, tr)
    X = F.assemble(base, pools, "combined")
    model = lgb.Booster(model_file=str(ROOT / "outputs/models/A_lgbm_combined.txt"))
    test_rows = np.flatnonzero(te)

    slot_records, bed_records = [], []
    picked_rows = []
    for t in slots:
        occ = np.flatnonzero((admit <= t) & (stops > t))
        if len(occ) == 0:
            continue
        shift, offset = divmod(t, C.SHIFT_HOURS)
        slot_no = S.slot_hours(C.PRIMARY_K).index(offset) + 1
        pick = pick_at.get(t)
        for q in occ:
            ci = int(run_patients[q])
            rh = int(t - admit[q])
            sc = float(s_te[offsets[ci] + rh])
            recent = any(t - 12 < u < t for u in reviews_by_pos.get(q, []))
            bed_records.append({"unit_hour": t, "patient_id": ids[ci], "record_hour": rh,
                                "score": sc, "recently_reviewed": recent,
                                "tier": "High" if sc >= hi_cut else "Medium" if sc >= med_cut else "Low",
                                "picked": bool(q == pick)})
        if pick is not None:
            ci = int(run_patients[pick])
            rh = int(t - admit[pick])
            picked_rows.append(test_rows[offsets[ci] + rh])
            slot_records.append({"unit_hour": t, "shift": int(shift) + 1, "slot": slot_no,
                                 "patient_id": ids[ci], "record_hour": rh,
                                 "row": int(test_rows[offsets[ci] + rh])})
    slots_df = pd.DataFrame(slot_records)
    contrib = model.predict(X.iloc[slots_df["row"].to_numpy()], pred_contrib=True)
    reasons = [E.why_now(X.iloc[row], contrib[i, :-1], list(X.columns), base, int(row))
               for i, row in enumerate(slots_df["row"].to_numpy())]
    slots_df["why_now"] = reasons

    # classify each pick for the app's legend
    pt = patients.loc[slots_df["patient_id"]]
    lead = pt["t_onset"].to_numpy() - slots_df["record_hour"].to_numpy()
    cls = S.classify(pt["t_onset"].to_numpy(), pt["group"].to_numpy(object),
                     np.arange(len(slots_df)), slots_df["record_hour"].to_numpy())
    slots_df["review_class"] = cls
    slots_df["lead_hours"] = lead
    slots_df.drop(columns="row").to_parquet(ART / "slots.parquet", index=False)
    pd.DataFrame(bed_records).to_parquet(ART / "beds.parquet", index=False)

    # timelines for every A test patient (only fields the app plots)
    h = hourly.loc[te, ["patient_id", "hour", "HR", "MAP", "Resp", "Temp", "Lactate", "WBC"]].copy()
    h["score"] = s_te
    h.to_parquet(ART / "timelines.parquet", index=False)
    reviews = []
    for q, times in reviews_by_pos.items():
        ci = int(run_patients[q])
        for u in times:
            reviews.append({"patient_id": ids[ci], "record_hour": int(u - admit[q])})
    pd.DataFrame(reviews).to_parquet(ART / "reviews.parquet", index=False)
    meta = patients.loc[ids, ["t_onset", "group", "age", "gender", "n_hours"]].reset_index()
    meta.to_parquet(ART / "patients.parquet", index=False)

    # results tables for Tab 2
    for f in ("results_table.csv", "paired_differences.csv", "hourly_metrics.csv",
              "failure_cases.json", "before_new_testing.csv", "utility_scores.csv",
              "null_check.json"):
        src = RES / f
        if src.exists():
            (ART / f).write_bytes(src.read_bytes())
    (ART / "tiers.json").write_text(json.dumps({"high": float(hi_cut), "medium": float(med_cut)}))
    print(f"artifacts: {len(slots_df)} slots, {len(bed_records)} bed states")


if __name__ == "__main__":
    main()
