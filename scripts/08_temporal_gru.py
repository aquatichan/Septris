"""Step 08: train a masked temporal GRU on exactly the frozen Septris split.

The model receives, at every ICU hour, (1) current physiologic values,
(2) measurement masks, and (3) log time since each measurement. This makes
irregular sampling explicit rather than treating imputation as an observation.
It predicts the existing 12-hour pre-onset target at every hour.

This is an exploratory comparator. It must be evaluated by the same
cross-hospital, capacity-limited review simulation as the pre-registered
LightGBM; a higher AUROC alone is not a deployment claim.
"""

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from src import config as C, data_io as D, features as F, labels as L

OUT = ROOT / "outputs"
SCORES = ROOT / "data/processed/scores"
MODELS = ROOT / "outputs/models"
NAME = "temporal_gru"
EPOCHS = 15
PATIENCE = 3
BATCH_SIZE = 16
HIDDEN = 64


def seed_everything(seed=C.SEED):
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
        torch.use_deterministic_algorithms(True, warn_only=True)
    except ImportError as e:
        raise RuntimeError("Temporal GRU requires PyTorch. Install torch before running scripts/08_temporal_gru.py.") from e


def load():
    df = pd.read_parquet(ROOT / "data/processed/hourly.parquet")
    df = df.sort_values(["patient_id", "hour"], kind="stable").reset_index(drop=True)
    patients = pd.read_csv(OUT / "patients.csv")
    df = L.add_target(df, patients)
    df["split"] = df["patient_id"].map(patients.set_index("patient_id")["split"])
    av = pd.read_csv(OUT / "availability.csv")
    variables = [v for v in D.MEASURED if v not in set(av.loc[av["flag_hospital_specific"], "variable"])]
    return df, variables


def patient_bounds(pid):
    start = np.flatnonzero(np.r_[True, pid[1:] != pid[:-1]])
    end = np.r_[start[1:], len(pid)]
    return start, end


class PatientSequences:
    """Creates causal sequence features lazily, keeping padded batches small."""

    def __init__(self, base, target, supervised, bounds, indices, median, scale):
        self.base, self.target, self.supervised, self.bounds = base, target, supervised, bounds
        self.indices, self.median, self.scale = np.asarray(indices), median, scale

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, i):
        a, b = self.bounds[0][self.indices[i]], self.bounds[1][self.indices[i]]
        cur = self.base["current"][a:b].astype(np.float32, copy=True)
        obs = (~np.isnan(cur)).astype(np.float32)
        val = np.nan_to_num((cur - self.median) / self.scale, nan=0.0, posinf=0.0, neginf=0.0)
        since = np.log1p(np.minimum(self.base["since"][a:b], 48.0)).astype(np.float32) / np.log(49.0)
        age = float(np.nan_to_num(self.base["age"][a], nan=0.0)) / 100.0
        sex = float(np.nan_to_num(self.base["gender"][a], nan=0.0))
        demo = np.column_stack([
            np.full(b - a, age, dtype=np.float32),
            np.full(b - a, sex, dtype=np.float32),
        ])
        return (np.concatenate([val, obs, since, demo], axis=1),
                self.target[a:b].astype(np.float32), self.supervised[a:b])


def collate(batch):
    import torch
    n = len(batch)
    lengths = np.asarray([len(x) for x, _, _ in batch], dtype=np.int64)
    width = batch[0][0].shape[1]
    x = np.zeros((n, lengths.max(), width), dtype=np.float32)
    y = np.zeros((n, lengths.max()), dtype=np.float32)
    valid = np.zeros((n, lengths.max()), dtype=bool)
    supervised = np.zeros((n, lengths.max()), dtype=bool)
    for i, (xi, yi, si) in enumerate(batch):
        x[i, :len(xi)] = xi
        y[i, :len(yi)] = yi
        valid[i, :len(xi)] = True
        supervised[i, :len(si)] = si
    return (torch.from_numpy(x), torch.from_numpy(y), torch.from_numpy(valid),
            torch.from_numpy(supervised), torch.from_numpy(lengths))


def build_model(width):
    import torch.nn as nn

    class TemporalGRU(nn.Module):
        def __init__(self):
            super().__init__()
            self.input = nn.Sequential(nn.Linear(width, HIDDEN), nn.ReLU(), nn.Dropout(0.10))
            self.gru = nn.GRU(HIDDEN, HIDDEN, num_layers=2, batch_first=True, dropout=0.15)
            self.head = nn.Linear(HIDDEN, 1)

        def forward(self, x, lengths):
            from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence
            x = self.input(x)
            packed = pack_padded_sequence(x, lengths.cpu(), batch_first=True, enforce_sorted=False)
            out, _ = self.gru(packed)
            out, _ = pad_packed_sequence(out, batch_first=True, total_length=x.shape[1])
            return self.head(out).squeeze(-1)

    return TemporalGRU()


def score(model, dataset, device, supervised_only=False):
    import torch
    from torch.utils.data import DataLoader
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=False, collate_fn=collate)
    model.eval()
    out = []
    with torch.no_grad():
        for x, _, _, supervised, lengths in loader:
            prob = torch.sigmoid(model(x.to(device), lengths.to(device))).cpu().numpy()
            for z, use, n in zip(prob, supervised.numpy(), lengths.numpy()):
                out.append(z[:n][use[:n]] if supervised_only else z[:n])
    return np.concatenate(out).astype(np.float32)


def main():
    import argparse
    import torch
    global NAME
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=C.SEED, help="extra seeds train ensemble members")
    ap.add_argument("--threads", type=int, default=0)
    args = ap.parse_args()
    if args.threads:
        torch.set_num_threads(args.threads)
    if args.seed != C.SEED:
        NAME = f"temporal_gru_s{args.seed}"
    from torch.nn import functional as nnf
    from torch.utils.data import DataLoader

    seed_everything(args.seed)
    SCORES.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    df, variables = load()
    base = F.causal_base(df, variables)
    pid = df["patient_id"].to_numpy()
    starts, ends = patient_bounds(pid)
    hospital, split = df["hospital"].to_numpy(), df["split"].to_numpy()
    y = df["target"].to_numpy(np.float32)
    in_training = df["in_training"].to_numpy(bool)
    patient_hospital = hospital[starts]
    patient_split = split[starts]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    report = {"architecture": {"name": "masked temporal GRU", "hidden": HIDDEN, "layers": 2,
              "inputs": "normalized current values, observation masks, log hours since measurement, age, sex"},
              "device": str(device), "models": {}}

    for H in C.HOSPITALS:
        tr_rows = (hospital == H) & (split == "train") & in_training
        va_rows = (hospital == H) & (split == "val") & in_training
        train_patients = np.flatnonzero((patient_hospital == H) & (patient_split == "train"))
        val_patients = np.flatnonzero((patient_hospital == H) & (patient_split == "val"))
        raw = base["current"][tr_rows]
        median = np.nanmedian(raw, axis=0).astype(np.float32)
        scale = np.nanstd(raw, axis=0).astype(np.float32)
        scale = np.where(scale < 1e-4, 1.0, scale)
        train_ds = PatientSequences(base, y, tr_rows, (starts, ends), train_patients, median, scale)
        val_ds = PatientSequences(base, y, va_rows, (starts, ends), val_patients, median, scale)
        width = train_ds[0][0].shape[1]
        model = build_model(width).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
        pos_weight = torch.tensor([(tr_rows.sum() - y[tr_rows].sum()) / max(y[tr_rows].sum(), 1)], device=device)
        train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate,
                                  generator=torch.Generator().manual_seed(args.seed))
        best, best_state, stale = -np.inf, None, 0
        history = []
        for epoch in range(1, EPOCHS + 1):
            model.train()
            losses = []
            for x, yy, _, supervised, lengths in train_loader:
                optimizer.zero_grad()
                logits = model(x.to(device), lengths.to(device))
                sup = supervised.to(device)
                loss = nnf.binary_cross_entropy_with_logits(logits[sup], yy.to(device)[sup],
                                                            pos_weight=pos_weight)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                losses.append(float(loss.detach().cpu()))
            val_score = score(model, val_ds, device, supervised_only=True)
            val_y = y[va_rows]
            pr = average_precision_score(val_y, val_score)
            auc = roc_auc_score(val_y, val_score)
            history.append({"epoch": epoch, "train_loss": float(np.mean(losses)), "val_pr_auc": float(pr), "val_auroc": float(auc)})
            print(f"[{H}] epoch {epoch}: loss {np.mean(losses):.4f}, val PR-AUC {pr:.4f}, AUROC {auc:.4f}", flush=True)
            if pr > best:
                best, stale = pr, 0
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            else:
                stale += 1
                if stale >= PATIENCE:
                    break
        model.load_state_dict(best_state)
        all_patients = np.arange(len(starts))
        all_ds = PatientSequences(base, y, np.ones(len(y), dtype=bool), (starts, ends), all_patients, median, scale)
        scores = score(model, all_ds, device)
        np.save(SCORES / f"{H}_{NAME}.npy", scores)
        torch.save({"state_dict": best_state, "median": median, "scale": scale, "variables": variables}, MODELS / f"{H}_{NAME}.pt")
        report["models"][H] = {"best_val_pr_auc": float(best), "history": history, "rows": int(len(scores))}
        (OUT / f"{NAME}_selection.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
