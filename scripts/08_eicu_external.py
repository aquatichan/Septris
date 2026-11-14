"""Step 8 (exploratory, post hoc): zero-shot test on a third hospital system.

eICU Collaborative Research Database demo v2.0.1 (open access, ODbL 1.0):
2,520 ICU stays from 186 US hospitals. It is converted to the Challenge's
hourly format, labelled with an approximation of the Challenge's Sepsis-3
definition, and scored by the FROZEN version 1 models trained at A or B.
Nothing is trained on eICU.

Label (fixed before any model was scored on eICU; see docs/eicu_external.md):
  t_suspicion = first systemic antibiotic order (not cancelled; cefazolin
                excluded as usual surgical prophylaxis). The demo has almost no
                culture records, so the Challenge's culture condition is dropped.
  t_SOFA      = first hour in [t_suspicion - 48 h, t_suspicion + 24 h] where
                SOFA rises >= 2 above its minimum so far in that window.
  t_sepsis    = min(t_suspicion, t_SOFA); SepsisLabel = 1 from t_sepsis - 6 h.

    python scripts/08_eicu_external.py --eicu /path/to/eicu-demo/data
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lightgbm as lgb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from src import config as C, data_io as D, features as F, labels as L, simulation as S  # noqa: E402

OUT = ROOT / "outputs/eicu"
MAX_HOURS = 336
ABX = ("vancomycin|piperacillin|zosyn|tazobactam|cefepime|maxipime|ceftriaxone|rocephin|meropenem|merrem|"
       "imipenem|ertapenem|levofloxacin|levaquin|ciprofloxacin|cipro|moxifloxacin|metronidazole|flagyl|"
       "azithromycin|ceftazidime|ampicillin|unasyn|clindamycin|gentamicin|tobramycin|linezolid|daptomycin|"
       "doxycycline|aztreonam|cefuroxime|cefoxitin|sulfamethoxazole|bactrim|nafcillin|oxacillin")
PRESSORS = "norepinephrine|levophed|epinephrine|dopamine|vasopressin|phenylephrine|neosynephrine"
LAB_MAP = {"lactate": "Lactate", "WBC x 1000": "WBC", "creatinine": "Creatinine", "platelets x 1000": "Platelets",
           "total bilirubin": "Bilirubin_total", "direct bilirubin": "Bilirubin_direct", "BUN": "BUN",
           "glucose": "Glucose", "pH": "pH", "paCO2": "PaCO2", "FiO2": "FiO2", "HCO3": "HCO3",
           "potassium": "Potassium", "chloride": "Chloride", "calcium": "Calcium", "magnesium": "Magnesium",
           "phosphate": "Phosphate", "AST (SGOT)": "AST", "alkaline phos.": "Alkalinephos", "Hgb": "Hgb",
           "Hct": "Hct", "PTT": "PTT", "fibrinogen": "Fibrinogen", "troponin - I": "TroponinI",
           "Base Excess": "BaseExcess", "O2 Sat (%)": "SaO2", "paO2": "_PaO2"}


def log(m):
    print(time.strftime("%H:%M:%S"), m, flush=True)


def hourly_median(df, stay, offset, cols):
    d = df[[stay, offset] + cols].copy()
    d = d[d[offset] >= 0]
    d["hour"] = (d[offset] // 60).astype(int)
    return d.groupby([stay, "hour"])[cols].median()


def convert(src: Path):
    pt = pd.read_csv(src / "patient.csv.gz")
    pt = pt[pt["unitdischargeoffset"] >= 8 * 60].copy()
    pt["n_hours"] = np.minimum(pt["unitdischargeoffset"] // 60, MAX_HOURS).astype(int)
    stays = set(pt["patientunitstayid"])
    log(f"{len(pt)} stays with >= 8 ICU hours")

    vp = pd.read_csv(src / "vitalPeriodic.csv.gz",
                     usecols=["patientunitstayid", "observationoffset", "heartrate", "sao2", "respiration",
                              "systemicsystolic", "systemicdiastolic", "systemicmean", "etco2"])
    vp = hourly_median(vp[vp.patientunitstayid.isin(stays)], "patientunitstayid", "observationoffset",
                       ["heartrate", "sao2", "respiration", "systemicsystolic", "systemicdiastolic",
                        "systemicmean", "etco2"])
    va = pd.read_csv(src / "vitalAperiodic.csv.gz",
                     usecols=["patientunitstayid", "observationoffset", "noninvasivesystolic",
                              "noninvasivediastolic", "noninvasivemean"])
    va = hourly_median(va[va.patientunitstayid.isin(stays)], "patientunitstayid", "observationoffset",
                       ["noninvasivesystolic", "noninvasivediastolic", "noninvasivemean"])
    nc = pd.read_csv(src / "nurseCharting.csv.gz",
                     usecols=["patientunitstayid", "nursingchartoffset", "nursingchartcelltypevallabel",
                              "nursingchartcelltypevalname", "nursingchartvalue"])
    nc = nc[nc.patientunitstayid.isin(stays)]
    nc["v"] = pd.to_numeric(nc["nursingchartvalue"], errors="coerce")
    temp = nc[(nc.nursingchartcelltypevallabel == "Temperature") &
              (nc.nursingchartcelltypevalname == "Temperature (C)")][["patientunitstayid", "nursingchartoffset", "v"]]
    temp = hourly_median(temp.rename(columns={"v": "Temp"}), "patientunitstayid", "nursingchartoffset", ["Temp"])
    gcs = nc[(nc.nursingchartcelltypevallabel == "Glasgow coma score") &
             (nc.nursingchartcelltypevalname == "GCS Total")][["patientunitstayid", "nursingchartoffset", "v"]]
    gcs = hourly_median(gcs.rename(columns={"v": "_GCS"}), "patientunitstayid", "nursingchartoffset", ["_GCS"])
    lab = pd.read_csv(src / "lab.csv.gz", usecols=["patientunitstayid", "labresultoffset", "labname", "labresult"])
    lab = lab[lab.patientunitstayid.isin(stays) & lab.labname.isin(LAB_MAP)]
    lab["col"] = lab["labname"].map(LAB_MAP)
    lab = lab[lab.labresultoffset >= 0]
    lab["hour"] = (lab.labresultoffset // 60).astype(int)
    lab = lab.pivot_table(index=["patientunitstayid", "hour"], columns="col", values="labresult", aggfunc="median")

    rows = []
    for r in pt.itertuples():
        rows.append(pd.DataFrame({"patientunitstayid": r.patientunitstayid, "hour": np.arange(r.n_hours)}))
    grid = pd.concat(rows, ignore_index=True).set_index(["patientunitstayid", "hour"])
    g = grid.join(vp, how="left").join(va, how="left").join(temp, how="left").join(gcs, how="left").join(lab, how="left")
    out = pd.DataFrame(index=g.index)
    out["HR"], out["O2Sat"], out["Temp"], out["Resp"], out["EtCO2"] = (
        g["heartrate"], g["sao2"], g["Temp"], g["respiration"], g["etco2"])
    for col, a, n in (("SBP", "systemicsystolic", "noninvasivesystolic"),
                      ("DBP", "systemicdiastolic", "noninvasivediastolic"),
                      ("MAP", "systemicmean", "noninvasivemean")):
        out[col] = g[a].where(g[a].notna(), g[n])
    for col in D.LABS:
        out[col] = g[col] if col in g else np.nan
    out["FiO2"] = np.where(out["FiO2"] > 1, out["FiO2"] / 100, out["FiO2"])
    # plausibility filters (eICU has free-text artefacts)
    for col, lo, hi in (("HR", 20, 250), ("O2Sat", 50, 100), ("Temp", 30, 43), ("Resp", 3, 60),
                        ("SBP", 40, 260), ("DBP", 15, 200), ("MAP", 25, 220)):
        out.loc[(out[col] < lo) | (out[col] > hi), col] = np.nan
    out["_PaO2"], out["_GCS"] = g.get("_PaO2"), g["_GCS"]
    out = out.reset_index()
    p = pt.set_index("patientunitstayid")
    age = p["age"].replace("> 89", "90")
    out["Age"] = out["patientunitstayid"].map(pd.to_numeric(age, errors="coerce"))
    out["Gender"] = out["patientunitstayid"].map((p["gender"] == "Male").astype(float))
    out["Unit1"] = out["patientunitstayid"].map((p["unittype"] == "MICU").astype(float))
    out["Unit2"] = out["patientunitstayid"].map((p["unittype"] == "SICU").astype(float))
    out["HospAdmTime"] = out["patientunitstayid"].map(p["hospitaladmitoffset"] / 60)
    out["ICULOS"] = out["hour"] + 1
    return out, pt, src


def sofa_hourly(h, src, stays):
    """Hourly SOFA from carried-forward values (24 h), vasopressors and GCS."""
    inf = pd.read_csv(src / "infusionDrug.csv.gz", usecols=["patientunitstayid", "drugname", "infusionoffset"])
    inf = inf[inf.patientunitstayid.isin(stays) & inf.drugname.str.lower().str.contains(PRESSORS, na=False)]
    inf = inf[inf.infusionoffset >= 0]
    inf["hour"] = (inf.infusionoffset // 60).astype(int)
    on = set(zip(inf.patientunitstayid, inf.hour))
    g = h.groupby("patientunitstayid")
    cf = {c: g[c].transform(lambda s: s.ffill(limit=24)) for c in
          ("Platelets", "Bilirubin_total", "Creatinine", "MAP", "_PaO2", "FiO2", "_GCS")}
    with np.errstate(invalid="ignore"):
        coag = np.select([cf["Platelets"] < 20, cf["Platelets"] < 50, cf["Platelets"] < 100, cf["Platelets"] < 150], [4, 3, 2, 1], 0)
        liver = np.select([cf["Bilirubin_total"] >= 12, cf["Bilirubin_total"] >= 6, cf["Bilirubin_total"] >= 2,
                           cf["Bilirubin_total"] >= 1.2], [4, 3, 2, 1], 0)
        renal = np.select([cf["Creatinine"] >= 5, cf["Creatinine"] >= 3.5, cf["Creatinine"] >= 2,
                           cf["Creatinine"] >= 1.2], [4, 3, 2, 1], 0)
        pressor = np.array([(s, hr) in on for s, hr in zip(h.patientunitstayid, h.hour)])
        pressor = pd.Series(pressor).groupby(h.patientunitstayid.to_numpy()).transform(
            lambda s: s.rolling(6, min_periods=1).max()).to_numpy().astype(bool)
        cardio = np.where(pressor, 3, np.where(cf["MAP"] < 70, 1, 0))
        pf = cf["_PaO2"] / cf["FiO2"].where(cf["FiO2"] > 0, 0.21).fillna(0.21)
        resp = np.select([pf < 100, pf < 200, pf < 300, pf < 400], [4, 3, 2, 1], 0)
        cns = np.select([cf["_GCS"] < 6, cf["_GCS"] < 10, cf["_GCS"] < 13, cf["_GCS"] < 15], [4, 3, 2, 1], 0)
    return pd.Series(coag + liver + renal + cardio + resp + cns, index=h.index)


def label(h, pt, src):
    med = pd.read_csv(src / "medication.csv.gz",
                      usecols=["patientunitstayid", "drugname", "drugstartoffset", "drugordercancelled", "routeadmin"])
    med = med[med.drugordercancelled.fillna("No") != "Yes"]
    name = med.drugname.str.lower().fillna("")
    route = med.routeadmin.astype(str).str.lower()
    abx = med[name.str.contains(ABX) & ~name.str.contains("cefazolin|ancef") &
              ~route.str.contains("topical|ophth|otic|ointment|inhal")]
    t_sus = (abx.groupby("patientunitstayid")["drugstartoffset"].min() / 60).apply(np.floor)
    stays = set(h.patientunitstayid)
    h = h.copy()
    h["SOFA"] = sofa_hourly(h, src, stays)
    t_sep = {}
    for sid, ts in t_sus.items():
        if sid not in stays:
            continue
        s = h.loc[h.patientunitstayid == sid, ["hour", "SOFA"]]
        w = s[(s.hour >= ts - 48) & (s.hour <= ts + 24)]
        if w.empty:
            continue
        rise = w["SOFA"].to_numpy() - np.minimum.accumulate(w["SOFA"].to_numpy())
        hit = np.flatnonzero(rise >= 2)
        if len(hit):
            t_sep[sid] = min(ts, w["hour"].iloc[hit[0]])
    t = h["patientunitstayid"].map(t_sep)
    h["SepsisLabel"] = (h["hour"] >= t - C.LABEL_LEAD_HOURS).astype(int)
    # Challenge convention: a patient labelled at hour 0 keeps the label; onset hours before
    # ICU admission are clipped by the record start
    return h, t_sep, t_sus


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eicu", required=True)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    h, pt, src = convert(Path(args.eicu))
    h, t_sep, t_sus = label(h, pt, Path(args.eicu))
    h["patient_id"] = "e" + h["patientunitstayid"].astype(str)
    h["hospital"] = "E"
    h = h.sort_values(["patient_id", "hour"], kind="stable").reset_index(drop=True)
    patients = L.patient_table(h)
    dx = pd.read_csv(Path(args.eicu) / "diagnosis.csv.gz", usecols=["patientunitstayid", "diagnosisstring"])
    dx_sep = set(dx.loc[dx.diagnosisstring.str.contains("sepsis", case=False), "patientunitstayid"])
    lab_sep = {int(p[1:]) for p in patients.loc[patients.sepsis == 1, "patient_id"]}
    allstays = {int(p[1:]) for p in patients.patient_id}
    label_check = {
        "stays": len(allstays), "hospitals": int(pt.hospitalid.nunique()),
        "labelled_septic": len(lab_sep), "septic_pct": round(100 * len(lab_sep) / len(allstays), 1),
        "groups": patients["group"].value_counts().to_dict(),
        "with_sepsis_diagnosis": len(dx_sep & allstays),
        "diagnosed_and_labelled": len(dx_sep & lab_sep),
        "labelled_share_with_diagnosis_pct": round(100 * len(dx_sep & lab_sep) / max(1, len(lab_sep)), 1),
        "diagnosed_share_labelled_pct": round(100 * len(dx_sep & lab_sep) / max(1, len(dx_sep & allstays)), 1),
    }
    (OUT / "label_check.json").write_text(json.dumps(label_check, indent=1))
    log(f"label check: {label_check}")
    patients.to_csv(OUT / "patients.csv", index=False)

    # ---- frozen version 1 models, zero-shot ----
    variables = json.loads((ROOT / "outputs/variables_used.json").read_text())["used"]
    sel = json.loads((ROOT / "outputs/model_selection.json").read_text())
    rows_ab = pd.read_parquet(ROOT / "data/processed/rows.parquet")
    hourly_ab = pd.read_parquet(ROOT / "data/processed/hourly.parquet").sort_values(
        ["patient_id", "hour"], kind="stable").reset_index(drop=True)
    base_ab = F.causal_base(hourly_ab, variables)
    del hourly_ab
    base_e = F.causal_base(h, variables)
    he = L.add_target(h, patients)
    y_e, intr_e = he["target"].to_numpy(), he["in_training"].to_numpy()
    scores = {"sirs": F.sirs_count(base_e).astype(float), "news": F.news_score(base_e)}
    avail = {}
    for H in C.HOSPITALS:
        tr = (rows_ab.hospital.to_numpy() == H) & (rows_ab.split.to_numpy() == "train") & rows_ab.in_training.to_numpy()
        pools = F.fit_pools(base_ab, tr)
        cur_ab, cur_e = F.current_values(base_ab, pools), F.current_values(base_e, pools)
        y_ab = rows_ab.target.to_numpy()
        sc = StandardScaler().fit(cur_ab.to_numpy()[tr])
        lr = LogisticRegression(class_weight="balanced", max_iter=1000).fit(sc.transform(cur_ab.to_numpy()[tr]), y_ab[tr])
        scores[f"{H}:lr"] = lr.predict_proba(sc.transform(cur_e.to_numpy()))[:, 1]
        for fs in ("values", "missing", "combined"):
            b = lgb.Booster(model_file=str(ROOT / f"outputs/models/{H}_lgbm_{fs}.txt"))
            X = F.assemble(base_e, pools, fs)
            assert list(X.columns) == sel[f"{H}_lgbm_{fs}"]["features"]
            scores[f"{H}:lgbm_{fs}"] = b.predict(X)
        log(f"[{H}] scored eICU zero-shot")
    for j, v in enumerate(variables):
        avail[v] = round(100 * base_e["observed"][:, j].mean(), 2)
    (OUT / "availability.json").write_text(json.dumps(avail, indent=1))

    hourly = [{"model": k, "auroc": roc_auc_score(y_e[intr_e], s[intr_e]),
               "pr_auc": average_precision_score(y_e[intr_e], s[intr_e])} for k, s in scores.items()]
    hourly = pd.DataFrame(hourly)
    hourly["prevalence"] = y_e[intr_e].mean()
    hourly.to_csv(OUT / "hourly_metrics.csv", index=False)
    print(hourly.round(3).to_string(index=False))

    ids = h["patient_id"].drop_duplicates().to_numpy()
    nh = h.groupby("patient_id", sort=False).size().loc[ids].to_numpy()
    p = patients.set_index("patient_id").loc[ids]
    coh = S.Cohort(nh, p["t_onset"].to_numpy(float), p["group"].to_numpy(object),
                   np.r_[0, np.cumsum(nh)[:-1]], {k: np.asarray(v, float) for k, v in scores.items()})
    pols = ["random"] + list(scores)
    point = pd.DataFrame([{"seed": s, "policy": k, **m} for s in C.SIM_SEEDS
                          for k, m in S.sweep(coh, pols, k=C.PRIMARY_K, seed=s)[0].items()])
    boot = []
    for bi in range(C.N_BOOT):
        idx = np.random.default_rng([2026, ord("E"), bi]).integers(0, len(ids), len(ids))
        for k, m in S.sweep(coh, pols, k=C.PRIMARY_K, seed=100_000 + bi, resample=idx)[0].items():
            boot.append({"rep": bi, "policy": k, **m})
    boot = pd.DataFrame(boot)
    pm = point.groupby("policy").mean(numeric_only=True)
    tab = []
    for pol in pols:
        g = boot[boot.policy == pol]
        lo, hi = np.nanpercentile(g["caught6"], [2.5, 97.5])
        tab.append({"policy": pol, "eligible": pm.loc[pol, "eligible"], "caught6_n": pm.loc[pol, "caught6_n"],
                    "caught6": pm.loc[pol, "caught6"], "caught6_lo": lo, "caught6_hi": hi,
                    "caught_any": pm.loc[pol, "caught_any"], "false_per_shift": pm.loc[pol, "false_per_shift"],
                    "median_lead": pm.loc[pol, "median_lead"]})
    tab = pd.DataFrame(tab)
    piv = boot.pivot_table(index="rep", columns="policy", values="caught6")
    diffs = []
    for a in [c for c in pols if c != "random"]:
        d = (piv[a] - piv["random"]).to_numpy()
        lo, hi = np.nanpercentile(d, [2.5, 97.5])
        diffs.append({"comparison": f"{a} minus random", "point": pm.loc[a, "caught6"] - pm.loc["random", "caught6"],
                      "lo": lo, "hi": hi, "excludes_zero": bool(lo > 0 or hi < 0)})
    tab.to_csv(OUT / "results_table.csv", index=False)
    pd.DataFrame(diffs).to_csv(OUT / "paired_differences.csv", index=False)
    print(tab.round(3).to_string(index=False))
    print(pd.DataFrame(diffs).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
