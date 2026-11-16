# SEPTRIS clinical decision-support API

> This project is a prototype and is not medical advice. It does not diagnose sepsis, recommend treatment, or connect to a live EHR.

## Purpose

The Gradio demo replays precomputed test-patient data. The API adds a separate,
replayable backend contract that demonstrates how a frozen model could be
connected to hourly EHR observations without changing the research result.

## What it scores with

The API serves the pre-registered **LightGBM combined** model for the chosen
source hospital, with at most five charts per queue (matching the
5-reviews-per-shift budget). It does not serve the later LightGBM + GRU blend
shown in the 3D demo, and its queue rule (a calibrated minimum priority, up to
five charts) is simpler than the shift-by-shift review simulation.

Replay check (14 Nov 2026): 25 Hospital A test patients were replayed through
the engine at three time points each (75 scores). With the dataset's own
patient ids the engine reproduced the evaluation scores exactly. With other
ids the scores differed slightly (mean absolute difference 0.012 on the 0–1
raw score, correlation 0.987), because gaps are filled with draws keyed to
the patient id.

Known limitation of the data-sufficiency rule (measured on test patients,
14 Nov 2026): requiring heart rate, systolic pressure, respiratory rate,
oxygen saturation **and** temperature all within two hours keeps a patient out
of the queue for about 35% of ICU hours at both hospitals, and for about 40%
of the hours that fall in the 12 hours before sepsis onset. Temperature is
the cause: it is charted in only about 70% of two-hour windows. The research
results do not use this rule. Before any real use, the rule should either
allow a longer window for temperature or queue such patients with a
"data missing" flag instead of dropping them.

## Safety properties

- **Fail closed:** no score is returned if the source-hospital model bundle is absent or its model-file SHA-256 digest does not match.
- **Immutable causal input:** observations are stored by ICU hour; corrections, duplicate hours, time reversal, and a source-hospital change are rejected rather than silently rewriting history.
- **Schema validation:** unknown fields, non-finite values, invalid ages, and malformed identifiers are rejected.
- **No automatic intervention:** the only output is a ranked clinician-review queue.
- **Capacity constraint:** at most three eligible charts are returned.
- **Snooze:** a reviewed chart is excluded for 12 clock hours.
- **Data sufficiency:** scores with no recent (within two hours) HR, SBP, respiratory rate, oxygen saturation, or temperature are never queued.
- **Familiarity:** source-training 1st–99th percentile ranges flag patterns outside the validated range; this makes uncertainty visible and does not convert a score into a recommendation.
- **Replay audit:** only HMAC hashes of identifier and payload are written to the audit table; reviewer identifiers are HMAC-hashed with a per-database secret.

## Frozen artifact contract

Run the exporter after training:

```bash
python scripts/11_export_model_bundle.py
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

The API only trusts local artifacts produced by this repository:

- `outputs/models/A_lgbm_combined.txt`
- `outputs/models/A_lgbm_combined.bundle.pkl`
- equivalents for hospital B.

The pickle bundle is a trusted local model artifact, never an uploaded API
input. It includes the exact feature order, training-hospital imputation pools,
source-validation Platt calibration, utility-selected queue threshold,
familiarity ranges, and the full SHA-256 digest of its paired model file.
The engine refuses a mismatched file, preventing a silently swapped or stale
model from being scored with the wrong calibration and threshold.

## Endpoints

- `POST /v1/observations`: validate, persist, score one hourly chart update.
- `GET /v1/queue?hospital=A`: obtain up to three unsnoozed charts for human review.
- `GET /v1/patients/{id}/timeline`: replay input history.
- `POST /v1/patients/{id}/review`: record a human chart-open event.
- `GET /health`: artifact readiness and model versions.

## What a real deployment still requires

Authentication/authorization, encrypted managed storage, FHIR/EHR integration,
hospital privacy/security review, prospectively defined workflow, clinician
ownership, independent calibration, fairness assessment, silent-mode
monitoring, and a prospective outcome study. This prototype does not
establish clinical effectiveness.
