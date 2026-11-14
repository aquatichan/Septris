"""Download and parse the PhysioNet 2019 patient files.

No modelling happens here. Works per hospital ("A" or "B").
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

PHYSIONET_BASE = "https://physionet.org/files/challenge-2019/1.0.0/training"
HOSPITAL_DIRS = {"A": "training_setA", "B": "training_setB"}

VITALS = ["HR", "O2Sat", "Temp", "SBP", "MAP", "DBP", "Resp", "EtCO2"]
LABS = [
    "BaseExcess", "HCO3", "FiO2", "pH", "PaCO2", "SaO2", "AST", "BUN",
    "Alkalinephos", "Calcium", "Chloride", "Creatinine", "Bilirubin_direct",
    "Glucose", "Lactate", "Magnesium", "Phosphate", "Potassium",
    "Bilirubin_total", "TroponinI", "Hct", "Hgb", "PTT", "WBC",
    "Fibrinogen", "Platelets",
]
DEMOGRAPHICS = ["Age", "Gender", "Unit1", "Unit2", "HospAdmTime", "ICULOS"]
LABEL = "SepsisLabel"
MEASURED = VITALS + LABS  # columns whose missingness reflects measurement

# The official label turns on 6 hours before clinical onset.
LABEL_LEAD_HOURS = 6
# Shortcut fields: never in the deployed model or the missingness-only model.
SHORTCUTS = ["ICULOS", "HospAdmTime", "Unit1", "Unit2"]


def download(data_dir: str | Path, hospitals=("A", "B")) -> Path:
    """Download the official compressed training archives, then unpack them.

    PhysioNet hosts the two public archives directly. Downloading two archives
    is far quicker and more reliable in a clean environment than recursively
    making about 40,000 individual file requests.
    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    for h in hospitals:
        destination = data_dir / HOSPITAL_DIRS[h]
        if any(destination.glob("*.psv")):
            continue
        archive = data_dir / f"training_set{h}.zip"
        url = f"{PHYSIONET_BASE}_set{h}.zip"
        subprocess.run(["wget", "-q", "-c", "-O", str(archive), url], check=True)
        staging = data_dir / f".unpack_{h}"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir()
        with zipfile.ZipFile(archive) as z:
            z.extractall(staging)
        source = staging / "training"
        if not source.exists():
            raise FileNotFoundError(f"Official archive {archive} did not contain training/")
        shutil.rmtree(destination, ignore_errors=True)
        shutil.move(str(source), str(destination))
        shutil.rmtree(staging)
    return data_dir

def load_hospital(data_dir: str | Path, hospital: str) -> pd.DataFrame:
    """Read every patient file for one hospital into one long table.

    Adds patient_id, hospital and hour (0-based row index within the stay).
    """
    folder = Path(data_dir) / HOSPITAL_DIRS[hospital]
    files = sorted(folder.glob("*.psv"))
    if not files:
        raise FileNotFoundError(f"No .psv files in {folder}. Run download() first.")
    frames = []
    for f in files:
        df = pd.read_csv(f, sep="|")
        df.insert(0, "hour", np.arange(len(df)))
        df.insert(0, "hospital", hospital)
        df.insert(0, "patient_id", f.stem)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def save_parquet(df: pd.DataFrame, path: str | Path) -> None:
    """Cache a loaded hospital so later sessions skip the slow CSV parsing."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
