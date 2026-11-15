"""Step 16: "Septris Lite", a small model that runs in the browser.

The 3D web app lets someone type in a new patient by hand. The full Septris
models need a patient's hourly history and run in Python, so the web page
uses this compact stand-in instead: a LightGBM model trained at Hospital A
on the same label (sepsis onset within 12 hours) but using only the current
value of the few readings the form asks for. Blank fields are passed as
missing, which LightGBM handles natively.

Its score is turned into a 0-100 percentile against Hospital A validation
hours, the same scale the app uses for Septris. Writes web/data/lite.json
(trees, percentile table, typical values) and outputs/lite_model.json
(validation and test AUROC, so the app can state honestly how much weaker
the stand-in is than the full model).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lightgbm as lgb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

from src import config as C, features as F  # noqa: E402

FIELDS = ["HR", "MAP", "Resp", "Temp", "O2Sat", "Lactate", "WBC", "Creatinine", "Platelets"]


def node(n):
    if "leaf_value" in n:
        return round(n["leaf_value"], 5)
    assert n["decision_type"] == "<="
    # [feature index, threshold, missing goes left?, left, right]
    return [n["split_feature"], round(n["threshold"], 4), 1 if n["default_left"] else 0,
            node(n["left_child"]), node(n["right_child"])]


def main():
    rows = pd.read_parquet(ROOT / "data/processed/rows.parquet")
    hourly = pd.read_parquet(ROOT / "data/processed/hourly.parquet").sort_values(
        ["patient_id", "hour"], kind="stable").reset_index(drop=True)
    variables = json.loads((ROOT / "outputs/variables_used.json").read_text())["used"]
    base = F.causal_base(hourly, variables)
    del hourly
    X = np.column_stack([base["current"][:, variables.index(v)] for v in FIELDS]
                        + [base["age"], base["gender"]]).astype(np.float32)
    names = FIELDS + ["Age", "Male"]
    y = rows["target"].to_numpy()
    hosp, split, ok = rows["hospital"].to_numpy(), rows["split"].to_numpy(), rows["in_training"].to_numpy()
    tr, va, te = [(hosp == "A") & (split == s) & ok for s in ("train", "val", "test")]
    pos = y[tr].sum()
    params = dict(objective="binary", num_leaves=15, learning_rate=0.06, min_data_in_leaf=200, feature_fraction=0.8,
                  lambda_l2=1.0, scale_pos_weight=(tr.sum() - pos) / pos, seed=C.SEED, verbose=-1, num_threads=2)
    w_va = np.where(y[va] == 1, params["scale_pos_weight"], 1.0)
    model = lgb.train(params, lgb.Dataset(X[tr], y[tr], feature_name=names),
                      valid_sets=[lgb.Dataset(X[va], y[va], weight=w_va)], num_boost_round=400,
                      callbacks=[lgb.early_stopping(30, verbose=False)])
    raw = model.predict(X, raw_score=True)
    full = np.load(ROOT / "data/processed/scores/A_blend.npy")
    report = {"fields": names, "n_trees": model.best_iteration,
              "auroc": {"lite_val": roc_auc_score(y[va], raw[va]), "lite_test": roc_auc_score(y[te], raw[te]),
                        "septris_test": roc_auc_score(y[te], full[te])}}
    report["auroc"] = {k: round(float(v), 3) for k, v in report["auroc"].items()}
    (ROOT / "outputs/lite_model.json").write_text(json.dumps(report, indent=1))

    dump = model.dump_model(num_iteration=model.best_iteration)
    all_va = (hosp == "A") & (split == "val")
    typical = {n: round(float(np.nanmedian(X[tr][:, i])), 1) for i, n in enumerate(names)}
    out = {"fields": names, "trees": [node(t["tree_structure"]) for t in dump["tree_info"]],
           "quantiles": [round(float(q), 4) for q in np.quantile(raw[all_va], np.linspace(0, 1, 201))],
           "typical": typical, **report}
    (ROOT / "web/data/lite.json").write_text(json.dumps(out, separators=(",", ":")))
    print(json.dumps(report), (ROOT / "web/data/lite.json").stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
