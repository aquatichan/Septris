"""Step 13: export the 3D web app's data (web/data/septris.json) from app/artifacts.

Run after 05_app_artifacts.py. The web app (web/) is static: it reads only
this JSON file, so it can be hosted anywhere (GitHub Pages, a Claude artifact,
python -m http.server).

Layout: column-oriented tables ({"cols": [...], "rows": [[...], ...]}) to keep
the file small. Patients are referenced by index into "patients".
"""

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

ART = ROOT / "app/artifacts"
OUT = ROOT / "web/data/septris.json"
TIER = {"Low": 0, "Medium": 1, "High": 2}


def clean(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    if isinstance(x, float):
        return round(x, 1)
    if hasattr(x, "item"):
        return clean(x.item())
    return x


def table(df, cols):
    return {"cols": cols, "rows": [[clean(v) for v in r] for r in df[cols].itertuples(index=False)]}


def main():
    slots = pd.read_parquet(ART / "slots.parquet")
    beds = pd.read_parquet(ART / "beds.parquet")
    tl = pd.read_parquet(ART / "timelines.parquet")
    rev = pd.read_parquet(ART / "reviews.parquet")
    meta = pd.read_parquet(ART / "patients.parquet")
    demo = json.loads((ART / "demo.json").read_text())
    examples = json.loads((ART / "examples.json").read_text())
    res = pd.read_csv(ART / "results_table.csv")

    pids = sorted(set(beds.patient_id))
    idx = {p: i for i, p in enumerate(pids)}
    meta = meta.set_index("patient_id").loc[pids].reset_index()
    tl = tl[tl.patient_id.isin(idx)]
    rev_by = rev.groupby("patient_id")["record_hour"].apply(sorted).to_dict()
    patients = []
    for r in meta.itertuples():
        t = tl[tl.patient_id == r.patient_id].sort_values("hour")
        patients.append({
            "age": clean(r.age), "sex": "M" if r.gender == 1 else "F",
            "onset": clean(r.t_onset), "group": r.group,
            "risk": [None if pd.isna(v) else int(round(v)) for v in t.percentile],
            "hr": [None if pd.isna(v) else int(round(v)) for v in t.HR],
            "map": [None if pd.isna(v) else int(round(v)) for v in t.MAP],
            "resp": [None if pd.isna(v) else int(round(v)) for v in t.Resp],
            "temp": [None if pd.isna(v) else round(float(v), 1) for v in t.Temp],
            "lactate": [[int(h), round(float(v), 1)] for h, v in zip(t.hour, t.Lactate) if not pd.isna(v)],
            "wbc": [[int(h), round(float(v), 1)] for h, v in zip(t.hour, t.WBC) if not pd.isna(v)],
            "reviews": [int(h) for h in rev_by.get(r.patient_id, [])],
        })

    slots = slots.assign(p=slots.patient_id.map(idx))
    beds = beds.assign(p=beds.patient_id.map(idx), tier=beds.tier.map(TIER),
                       percentile=beds.percentile.round().astype(int))
    beds = beds.sort_values(["unit_hour", "bed"])

    def pol(T, key, k, home=True):
        if key in ("sirs", "random"):
            name = key
        else:
            H = T if home else ("B" if T == "A" else "A")
            name = f"{H}:{key}"
        r = res[(res.test == T) & (res.k == k) & (res.subgroup == "all") & (res.policy == name)]
        if r.empty:
            return None
        r = r.iloc[0]
        return {"caught": round(100 * r.caught6, 1), "lo": round(100 * r.caught6_lo, 1),
                "hi": round(100 * r.caught6_hi, 1), "false_per_shift": round(r.false_per_shift, 2),
                "eligible": int(r.eligible)}

    results = {str(k): {T: {"septris": pol(T, "blend", k), "septris_new_hospital": pol(T, "blend", k, False),
                            "lightgbm": pol(T, "lgbm_combined", k), "gru": pol(T, "temporal_gru", k),
                            "sirs": pol(T, "sirs", k), "random": pol(T, "random", k)} for T in "AB"}
               for k in (1, 2, 3, 5)}

    hm = pd.read_csv(ART / "hourly_metrics.csv")
    ut = pd.read_csv(ART / "utility_scores.csv")
    names = {"blend": "septris", "lgbm_combined": "lightgbm", "temporal_gru": "gru"}
    quality = {}
    for m, key in names.items():
        for r in hm[hm.model == m].itertuples():
            quality.setdefault(f"{r.train}>{r.test}", {})[key] = {"auroc": round(r.auroc, 3)}
        for r in ut[ut.model == m].itertuples():
            quality[f"{r.train}>{r.test}"][key]["utility"] = round(r.test_utility, 3)
    out = {
        "quality": quality,
        "meta": {k: demo[k] for k in ("k", "beds", "patients", "eligible_septic", "days", "policy_label",
                                      "model_text", "kind")},
        "slots": table(slots, ["unit_hour", "day", "clock", "shift_name", "shift", "check", "bed", "p",
                               "record_hour", "reasons", "driver", "pct_lgbm", "pct_gru", "review_class",
                               "lead_hours", "random_bed", "random_class", "sepsis_so_far", "sb_caught_so_far",
                               "random_caught_so_far"]),
        "beds": table(beds, ["unit_hour", "bed", "p", "hours_in_icu", "record_hour", "percentile", "tier",
                             "snoozed", "hours_since_check", "picked", "random_pick", "hours_to_sepsis", "rank",
                             "candidates"]),
        "patients": patients,
        "examples": examples,
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"{OUT} {OUT.stat().st_size / 1e6:.1f} MB, {len(patients)} patients, {len(slots)} reviews")


if __name__ == "__main__":
    main()
