"""Step 9 (exploratory, post hoc): third-hospital deterioration check.

PhysioNet/CinC Challenge 2012 (open access, ODC-By 1.0): 12,000 ICU stays,
first 48 hours, with in-hospital death, SOFA and SAPS-I for every stay.
There is no sepsis label, so this asks a narrower, label-free question:
do the FROZEN version 1 Septris scores rise for patients who go on to
die in hospital, and how does that compare with established severity scores?

Records are converted to the 2019 hourly format (hours 0-47). Gaps the 2012
data never records (pulse-oximetry SpO2, several labs) stay missing, which
the models then handle as unmeasured.

    python scripts/09_challenge2012_check.py --data data/raw/challenge2012
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lightgbm as lgb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

from src import config as C, data_io as D, features as F  # noqa: E402

OUT = ROOT / "outputs/challenge2012"
MAP = {"HR": "HR", "Temp": "Temp", "RespRate": "Resp", "SaO2": "SaO2", "FiO2": "FiO2", "pH": "pH",
       "PaCO2": "PaCO2", "HCO3": "HCO3", "BUN": "BUN", "Creatinine": "Creatinine", "Glucose": "Glucose",
       "Lactate": "Lactate", "Mg": "Magnesium", "K": "Potassium", "HCT": "Hct", "Platelets": "Platelets",
       "WBC": "WBC", "Bilirubin": "Bilirubin_total", "AST": "AST", "ALP": "Alkalinephos", "TroponinI": "TroponinI"}
BP = {"SBP": ("SysABP", "NISysABP"), "DBP": ("DiasABP", "NIDiasABP"), "MAP": ("MAP", "NIMAP")}


def load(data: Path):
    rows = []
    for s in ("a", "b", "c"):
        for f in sorted((data / f"set-{s}").glob("*.txt")):
            d = pd.read_csv(f)
            rid = int(d.loc[d.Parameter == "RecordID", "Value"].iloc[0])
            static = d[d.Time == "00:00"].set_index("Parameter")["Value"]
            ts = d[~d.Parameter.isin(["RecordID", "Age", "Gender", "Height", "ICUType", "Weight"])].copy()
            ts["hour"] = ts.Time.str.split(":").apply(lambda x: int(x[0]))
            ts = ts[(ts.hour >= 0) & (ts.hour < 48) & (ts.Value >= 0)]
            wide = ts.pivot_table(index="hour", columns="Parameter", values="Value", aggfunc="median")
            wide = wide.reindex(range(48))
            out = pd.DataFrame(index=range(48))
            for src, dst in MAP.items():
                out[dst] = wide[src] if src in wide else np.nan
            for dst, (inv, non) in BP.items():
                a = wide[inv] if inv in wide else pd.Series(np.nan, index=wide.index)
                n = wide[non] if non in wide else pd.Series(np.nan, index=wide.index)
                out[dst] = a.where(a > 0, n)
            out["FiO2"] = np.where(out["FiO2"] > 1, out["FiO2"] / 100, out["FiO2"])
            for col in D.MEASURED:
                if col not in out:
                    out[col] = np.nan
            age, sex = static.get("Age", np.nan), static.get("Gender", np.nan)
            out["Age"] = np.nan if age < 0 else age
            out["Gender"] = np.nan if sex < 0 else sex   # 2012: 1 = male, as in 2019
            out["ICULOS"] = np.arange(1, 49)
            out["HospAdmTime"], out["Unit1"], out["Unit2"] = np.nan, np.nan, np.nan
            out["SepsisLabel"] = 0
            out["patient_id"] = f"c{rid}"
            out["hour"] = np.arange(48)
            out["set"] = s
            rows.append(out)
    h = pd.concat(rows, ignore_index=True)
    outcomes = pd.concat([pd.read_csv(data / f"Outcomes-{s}.txt") for s in "abc"], ignore_index=True)
    outcomes["patient_id"] = "c" + outcomes["RecordID"].astype(str)
    return h.sort_values(["patient_id", "hour"], kind="stable").reset_index(drop=True), outcomes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data/raw/challenge2012"))
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    h, outcomes = load(Path(args.data))
    variables = json.loads((ROOT / "outputs/variables_used.json").read_text())["used"]
    sel = json.loads((ROOT / "outputs/model_selection.json").read_text())
    base_c = F.causal_base(h, variables)
    rows_ab = pd.read_parquet(ROOT / "data/processed/rows.parquet")
    hab = pd.read_parquet(ROOT / "data/processed/hourly.parquet").sort_values(
        ["patient_id", "hour"], kind="stable").reset_index(drop=True)
    base_ab = F.causal_base(hab, variables)
    del hab

    scores = {"sirs": F.sirs_count(base_c).astype(float), "news": F.news_score(base_c)}
    for H in C.HOSPITALS:
        tr = (rows_ab.hospital.to_numpy() == H) & (rows_ab.split.to_numpy() == "train") & rows_ab.in_training.to_numpy()
        pools = F.fit_pools(base_ab, tr)
        for fs in ("values", "missing", "combined"):
            b = lgb.Booster(model_file=str(ROOT / f"outputs/models/{H}_lgbm_{fs}.txt"))
            X = F.assemble(base_c, pools, fs)
            assert list(X.columns) == sel[f"{H}_lgbm_{fs}"]["features"]
            scores[f"{H}:lgbm_{fs}"] = b.predict(X)

    pid = h["patient_id"].to_numpy()
    first24 = h["hour"].to_numpy() < 24
    oc = outcomes.set_index("patient_id")
    res = []
    for window, mask in (("first 24 h", first24), ("first 48 h", np.ones(len(h), bool))):
        for name, s in scores.items():
            m = pd.Series(s[mask]).groupby(pid[mask]).max()
            y = oc.loc[m.index, "In-hospital_death"].to_numpy()
            res.append({"window": window, "score": name, "auroc_death": roc_auc_score(y, m.to_numpy())})
    y = oc["In-hospital_death"].to_numpy()
    for col in ("SOFA", "SAPS-I"):
        ok = oc[col] >= 0
        res.append({"window": "first 24 h (dataset field)", "score": col,
                    "auroc_death": roc_auc_score(y[ok], oc.loc[ok, col])})
    res = pd.DataFrame(res)
    res.to_csv(OUT / "death_auroc.csv", index=False)
    cov = {v: round(100 * base_c["observed"][:, j].mean(), 2) for j, v in enumerate(variables)}
    meta = {"stays": int(h.patient_id.nunique()), "in_hospital_death_pct": round(100 * y.mean(), 1),
            "coverage_pct_of_hours": cov}
    (OUT / "summary.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps({k: v for k, v in meta.items() if k != "coverage_pct_of_hours"}))
    print(res.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
