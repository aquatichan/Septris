"""Reasons for a temporal GRU pick, by occlusion.

For the patient's record up to the current hour, each variable in turn is
made to look unmeasured for the last 12 hours (value 0, observed mask 0,
hours-since at its cap). The drop in the current-hour risk is that variable's
contribution. The top three positive drops become plain-language reasons
that cite only real, measured values. These are model associations, not a
diagnosis.
"""

import importlib.util
from pathlib import Path

import numpy as np

from .explanations import LABEL, _num

ROOT = Path(__file__).resolve().parents[1]
WINDOW = 12


def load(hospital: str):
    import torch
    spec = importlib.util.spec_from_file_location("temporal_gru", ROOT / "scripts/08_temporal_gru.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ck = torch.load(ROOT / f"outputs/models/{hospital}_temporal_gru.pt", weights_only=False)
    n = len(ck["variables"])
    model = mod.build_model(3 * n + 2)
    model.load_state_dict(ck["state_dict"])
    model.eval()
    return mod, model, ck


def reasons(mod, model, ck, base, start: int, row: int, top: int = 3) -> list[str]:
    """start: first row of the patient; row: current row (both in base)."""
    import torch
    ds = mod.PatientSequences(base, np.zeros(row + 1), np.zeros(row + 1, bool),
                              (np.array([start]), np.array([row + 1])), np.array([0]),
                              ck["median"], ck["scale"])
    x, _, _ = ds[0]
    n = len(ck["variables"])
    h = len(x) - 1
    lo = max(0, h - WINDOW + 1)
    batch = np.repeat(x[None].astype(np.float32), n + 1, axis=0)
    for j in range(n):
        batch[j + 1, lo:, j] = 0.0
        batch[j + 1, lo:, n + j] = 0.0
        batch[j + 1, lo:, 2 * n + j] = 1.0
    with torch.no_grad():
        lengths = torch.full((n + 1,), len(x), dtype=torch.int64)
        risk = torch.sigmoid(model(torch.from_numpy(batch), lengths))[:, h].numpy()
    drop = risk[0] - risk[1:]
    out = []
    for j in np.argsort(-drop):
        if drop[j] <= 0 or len(out) == top:
            break
        var = ck["variables"][j]
        label, unit = LABEL.get(var, (var, ""))
        cur = base["current"][row, base["variables"].index(var)]
        if np.isnan(cur):
            out.append(f"a recent {label} measurement pattern")
        else:
            out.append(f"recent {label} readings (latest {_num(var, cur)} {unit})".replace(" )", ")"))
    return out
