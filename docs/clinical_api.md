# SEPTRIS clinical decision-support API

> This project is a prototype and is not medical advice. It does not diagnose sepsis, recommend treatment, or connect to a live EHR.

## Purpose

The Gradio demo replays precomputed test-patient data. The API adds a separate,
replayable backend contract that demonstrates how a frozen model could be
connected to hourly EHR observations without changing the research result.

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
