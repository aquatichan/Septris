# SignalBridge

**A safety-aware sepsis escalation queue for a capacity-constrained ICU.**
Veritas AI International High School Hackathon 2026, AI + Health track.
Team: Miheer Parasnis, Aaron Qin, Reyansh Maheshwari.

> **This project is a prototype and is not medical advice.**
> It does not diagnose sepsis or recommend treatment. It prioritizes which
> patients get a limited number of human chart reviews per shift.

## The question

Can an AI queue catch more upcoming sepsis cases at a fixed review budget
(3 reviews per 20-patient, 12-hour shift) than equal-budget random,
clinical-rule and simple machine-learning policies, and how much does that
change at a hospital system it never saw?

## Data

Public [PhysioNet/Computing in Cardiology Challenge 2019](https://physionet.org/content/challenge-2019/1.0.0/)
training data: hourly ICU records from two hospital systems
(set A, 20,336 patients; set B, 20,000 patients). Raw data is not committed;
the setup script downloads it.

## Setup

```bash
pip install -r requirements.txt
python scripts/setup_data.py          # downloads A and B, builds splits and audit
python -m pytest -q tests             # runs on synthetic data, no download needed
```

In Colab, open `notebooks/01_data_audit.ipynb` and run all cells.

`scripts/setup_data.py` writes to `outputs/`:

| File | Contents |
| --- | --- |
| `patients.csv` | One row per patient: hospital, stay length, sepsis, onset hour |
| `splits.csv` | Fixed 70/15/15 patient-level split per hospital (seed 42) |
| `split_summary.csv` | Patients and sepsis rate per hospital and split |
| `availability.csv` | How often each variable is recorded at each hospital, with both drop rules |
| `data_audit.csv` | Cohort summary per hospital |

## Key design rules

- Split by patient, never by row. Each hospital is split on its own, so
  A→A, B→B, A→B and B→A test on fixed patients.
- Onset `t_onset` = first hour with `SepsisLabel = 1`, plus 6 hours.
  Patients whose label is already on at hour 0 are flagged `onset_censored`
  and excluded from lead-time metrics.
- `ICULOS`, `HospAdmTime`, `Unit1` and `Unit2` are shortcuts: never in the
  deployed model or the missingness-only model.
- Everything that learns (imputation, calibration, thresholds) is fit on the
  training hospital only.

The full method, metrics and limitations are in the project brief.

## Repository layout

```
src/        data_io, labels, splits, audit (more modules as they are built)
scripts/    command-line entry points
notebooks/  Colab notebooks, in run order
tests/      tests on synthetic PhysioNet-format data
```

## AI assistance

Parts of the code and planning were drafted with Claude (Anthropic) and
reviewed by the team.
