"""Fixed-template "why now" lines from LightGBM feature contributions.

Only features that raised the score are used, at most three, each filled
with the patient's real value at that hour. Missingness features are worded
as a measurement pattern, never as clinician intent.
"""

import numpy as np

LABEL = {
    "HR": ("heart rate", "bpm"), "O2Sat": ("oxygen saturation", "%"), "Temp": ("temperature", "°C"),
    "SBP": ("systolic BP", "mmHg"), "MAP": ("MAP", "mmHg"), "DBP": ("diastolic BP", "mmHg"),
    "Resp": ("respiratory rate", "/min"), "Lactate": ("lactate", "mmol/L"), "WBC": ("WBC", "×10³/µL"),
    "Creatinine": ("creatinine", "mg/dL"), "Platelets": ("platelets", "×10³/µL"),
    "BUN": ("BUN", "mg/dL"), "Glucose": ("glucose", "mg/dL"), "pH": ("pH", ""),
    "PaCO2": ("PaCO2", "mmHg"), "FiO2": ("FiO2", ""), "HCO3": ("bicarbonate", "mmol/L"),
    "Bilirubin_total": ("bilirubin", "mg/dL"), "Hgb": ("hemoglobin", "g/dL"), "Hct": ("hematocrit", "%"),
    "Potassium": ("potassium", "mmol/L"), "BaseExcess": ("base excess", "mmol/L"),
}


def _name(v):
    return LABEL.get(v, (v, ""))


def phrase(feature: str, X_row, base: dict, row: int) -> str | None:
    if feature.startswith("m_"):
        var = feature[2:].rsplit("_", 1)[0]
        return f"a recent {_name(var)[0]} measurement pattern"
    if feature in ("age", "sex"):
        return None
    if feature == "shock_index":
        return f"shock index {X_row['shock_index']:.2f}"
    if feature.endswith("_delta"):
        var = feature[:-6]
        j = base["variables"].index(var)
        d = base["delta"][row, j]
        if np.isnan(d):
            return None
        word = "up" if d > 0 else "down"
        label, unit = _name(var)
        return f"{label} {word} {abs(d):.0f} {unit} since the previous reading".replace("  ", " ")
    for stat, word in (("_max6", "6-hour high"), ("_min6", "6-hour low"), ("_mean6", "6-hour average")):
        if feature.endswith(stat):
            var = feature[: -len(stat)]
            label, unit = _name(var)
            return f"{label} {word} {X_row[feature]:.0f} {unit}".strip()
    if feature in base["variables"]:
        j = base["variables"].index(feature)
        cur = base["current"][row, j]
        if np.isnan(cur):
            return None  # value was gap-filled, not measured: never cite it
        label, unit = _name(feature)
        fmt = f"{cur:.2f}" if abs(cur) < 10 else f"{cur:.0f}"
        return f"{label} {fmt} {unit}".strip()
    return None


def why_now(X_row, contrib: np.ndarray, columns: list[str], base: dict, row: int, top: int = 3) -> str:
    order = np.argsort(-contrib)
    parts = []
    for i in order:
        if contrib[i] <= 0 or len(parts) == top:
            break
        p = phrase(columns[i], X_row, base, row)
        if p and p not in parts:
            parts.append(p)
    if not parts:
        return "Priority came from several small contributions. These are model associations, not a diagnosis."
    return ("Priority rose with " + ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "")
            + parts[-1] + ". These are model associations, not a diagnosis.")
