"""Materialize the per-source winner from the validation-only robust-model gate.

The gate can select a different candidate for Hospital A and Hospital B.  This
script copies only those already-trained score arrays into the neutral name
``robust_selected``.  It does not read test labels or compute a metric; that
makes it safe to call before the single held-out evaluation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np

from src import config as C

SCORES = ROOT / "data" / "processed" / "scores"
GATE = ROOT / "outputs" / "robust_candidate_selection.json"
OUT = ROOT / "outputs" / "robust_selected_manifest.json"


def main():
    if not GATE.exists():
        raise FileNotFoundError("run scripts/17_candidate_gate.py before materializing a candidate")
    gate = json.loads(GATE.read_text())
    if "selected" not in gate:
        raise ValueError("candidate gate report has no selected models")
    manifest = {"protocol": "names selected by source-validation gate; no test labels read", "selected": {}}
    for source in C.HOSPITALS:
        chosen = gate["selected"].get(source)
        if not isinstance(chosen, str) or not chosen.replace("_", "").isalnum():
            raise ValueError(f"invalid selected candidate for {source}: {chosen!r}")
        src, dst = SCORES / f"{source}_{chosen}.npy", SCORES / f"{source}_robust_selected.npy"
        if not src.exists():
            raise FileNotFoundError(f"candidate selected by gate is missing: {src}")
        arr = np.load(src)
        np.save(dst, arr.astype(np.float32, copy=False))
        manifest["selected"][source] = {"candidate": chosen, "score_file": str(dst.relative_to(ROOT)),
                                         "rows": int(len(arr))}
        print(f"{source}: {chosen} -> {dst.name}")
    OUT.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
