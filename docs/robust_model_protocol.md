# Robust temporal-model protocol (exploratory, validation-gated)

> This project is a prototype and is not medical advice.

This is a next-round research protocol. It does **not** change the frozen
LightGBM result or turn an exploratory model into a clinical claim.

## Why these candidates

The current masked temporal GRU sees values, a flag showing whether each value
was measured, and time since its last measurement. That is useful in the
Challenge data, but order patterns can differ between hospitals. We therefore
test two stricter candidates:

| Candidate | Inputs / target | What it tests |
| --- | --- | --- |
| `gru_early_values` | Values + age/sex only; 6-12 hour target | Can physiology alone prioritize the reviews that matter? |
| `gru_early_maskdrop` | Masked GRU; 6-12 hour target; 15% training-only measurement dropout | Does masking order information during training make the trajectory model less brittle? |

The 1-5 hours before onset are excluded from the early-window candidate loss,
rather than being called negative. The model should not learn that danger
falls immediately before onset merely because the queue metric cannot count
that as an early catch.

## Locked selection sequence

1. Keep the patient-level A/B train/validation/test split unchanged.
2. Train both candidates using only the source hospital's training patients:

   ```bash
   python scripts/08_temporal_gru.py --input-mode values_only --target-window early_6_12 --name gru_early_values
   python scripts/08_temporal_gru.py --input-mode masked --target-window early_6_12 --measurement-dropout 0.15 --name gru_early_maskdrop
   ```

3. Run `python scripts/17_candidate_gate.py --candidates temporal_gru,gru_early_values,gru_early_maskdrop`.
   It selects separately for A and B using only home-hospital validation
   patients and the actual 20-bed, 3-review simulation.
4. If a candidate does not beat the existing GRU on source validation, stop:
   it is not run on test patients.
5. Freeze the winning name and evaluate it once on all four held-out
   train-to-test pairs. Report home and unseen-hospital results side by side,
   with paired patient-bootstrap intervals against the original GRU and the
   pre-registered LightGBM.

## What would count as success

A higher home score alone is not enough. The promising result would be a
validation-selected candidate with a paired, held-out improvement in early
catches at the unseen hospital **without** more false reviews per shift. If
that does not happen, retain the simpler existing model and report that
measurement-pattern robustness came at a performance cost.

## What cannot be honestly solved with this dataset

The Challenge files contain hourly vitals and labs, but not clinical notes,
medications, microbiology, prior admissions, order timestamps, or continuous
waveforms. No architecture can infer those missing signals. A hospital-ready
model needs a prospective, locally governed EHR extract with a new label
definition and a silent trial. The repository's external-data contract and
`docs/external_validation_protocol.md` specify that work; external data must
not be pooled into this development cohort.
