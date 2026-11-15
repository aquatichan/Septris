# External validation protocol

> This project is a prototype and is not medical advice.

## Purpose

External data are used to test a **frozen** SignalBridge/SEPTRIS model, not to
increase its reported development performance. Do not pool external rows into
Hospitals A/B training data during the hackathon.

## Access and handling

MIMIC-IV, full eICU, and HiRID are credentialed datasets. Every person who
touches a source must hold their own approved access and follow that source's
data-use agreement. Do not upload raw source data, patient-level extracts,
model bundles derived from restricted data, access tokens, or screenshots to
this repository or an external LLM service.

The repository accepts only local paths to authorized extracts. Run
`scripts/12_external_audit.py` on the machine that legitimately stores them.

## Canonical extract contract

One row per patient per ICU hour:

- Required: `patient_id`, `hour`
- Optional compatible measurements: the PhysioNet 2019 vital/lab names, in
  source-documented units.
- Static columns allowed: `Age`, `Gender`.
- Do not include any target, sepsis label, order, culture, antibiotic,
  vasopressor, ventilation, fluid, or treatment fields in the scoring extract.
  Those can become direct or indirect post-treatment leakage.
- Patient-hour rows must be unique and strictly increasing.
- Keep an external, access-controlled provenance note with dataset version,
  query, unit mapping, missingness profile, label specification, and date.

The audit gate fails on suspected treatment/label columns, duplicate time
points, time reversal, or fewer than eight compatible measurements.

## Labels

Do not reuse the Challenge 2019 label blindly. For each external source,
pre-register a Sepsis-3-style label reconstruction independent of the score
inputs, including:

1. The infection-suspicion rule and timestamps.
2. The organ dysfunction calculation.
3. Explicit treatment/order exclusion from features.
4. The time-zero and 6–12 hour evaluation window.
5. Which cases cannot be labeled reliably and are excluded.

Keep the label table access-controlled and join it only inside the authorized
analysis environment after feature scoring. Report its uncertainty rather than
silently treating it as ground truth.

## Required analyses

For each new source:

1. Run the contract audit and publish only aggregate coverage statistics.
2. Score the frozen A-trained and B-trained models without retraining.
3. Compare calibration, hourly AUROC/PR-AUC, official-style utility where the
   label supports it, and the fixed 20-bed/3-review queue simulation.
4. Report a physiology-only model separately from the combined model.
5. Report performance by hospital/unit where identifiers are permitted.
6. If local adaptation is attempted, fit it only on a separately held local
   calibration split, then evaluate it on a later unseen local test split.

A model must not be called portable because it improves on its development
hospitals. External performance, calibration, false reviews per shift, and
lead time are all required.
