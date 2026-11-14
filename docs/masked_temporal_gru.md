# Masked temporal GRU experiment

> This experiment is exploratory. This project is a prototype and is not medical advice.

## Purpose

The original Septris candidate is a LightGBM ranking model over causal,
engineered hourly features. This branch tests whether a causal sequence model can
use the order of measurements and physiologic changes more effectively without
using a future hour.

The model is deliberately named **masked temporal GRU**, not GRU-D: it is a
two-layer, unidirectional GRU with a learned input projection. At every hour it
receives normalized current values, an observation mask, log time since the last
measurement, age, and sex. Values, scaling statistics, and early stopping are
fit only on the source hospital's training/validation partitions. ICU length of
stay, admission time, unit type, and variables essentially absent at either
hospital are excluded.

## Result of the completed reproducible run

Same 20-bed, 3-review-per-12-hour-shift simulation; figures are shares of
eligible septic test patients reviewed 6–12 hours before recorded onset.

| Train → test | LightGBM combined | Masked temporal GRU | Difference |
| --- | ---: | ---: | ---: |
| A → A | 25.1% | 27.9% | +2.8 points |
| B → A | 15.5% | 19.4% | +3.9 points |
| B → B | 26.3% | 30.1% | +3.9 points |
| A → B | 23.7% | 25.4% | +1.6 points |

Hourly PR-AUC improved in all four comparisons. Official PhysioNet utility
improved in A→A, B→A, and B→B, but fell slightly in A→B. The original run did
not include a paired GRU-versus-LightGBM interval; this branch adds that
calculation in `scripts/03_evaluate.py`. Until that rerun is complete, none of
the differences above should be described as statistically distinguishable.

## Interpretation

The result supports further evaluation, not deployment. It is a modest absolute
gain at the fixed review budget and does not demonstrate that Septris
detects sepsis before clinicians, saves lives, or transfers safely. The target
is partially entangled with testing and treatment workflow, and the model has
only retrospective data from two systems.

## Reproduce

```bash
pip install -r requirements.txt
python scripts/01_audit.py --download
make reproduce
```

The temporal model is trained by `scripts/08_temporal_gru.py`, then evaluated
by the same patient-level split, unseen-hospital comparisons, bootstrap, and
capacity-limited simulator as LightGBM. `tests/test_temporal_gru.py` protects
the patient boundary and prevents post-onset rows from silently entering the
training-loss mask.

## Next experiments, in order

1. Re-run with the paired bootstrap comparison now included here.
2. Tune only on source validation data: history length, hidden width, dropout,
   learning rate, and class weighting. Freeze choices before opening tests.
3. Add a decision-aligned ranking loss for the three review slots, and compare
   it to binary cross-entropy using the same simulator.
4. Test a simple temporal convolutional network as a matched alternative before
   attempting a transformer. Do not add complexity unless it improves the
   cross-hospital, capacity-limited outcome.
5. Estimate the oracle catch ceiling under the same bed schedule. If the ceiling
   is near 30%, claiming 50% under this fixed budget is mathematically
   impossible, not a model-tuning failure.
