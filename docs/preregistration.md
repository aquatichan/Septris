# Pre-registration

Committed before any model was trained or any test-set number was computed.
The git timestamp of this file is the freeze time. Values are also in
`src/config.py`.

**Rule:** nothing in this table changes after the first external test
result. Any bug-forced change is logged at the bottom with the reason and time.

| Frozen item | Value |
| --- | --- |
| Data | PhysioNet/CinC Challenge 2019 training sets A (20,336 patients) and B (20,000) |
| Onset | T_onset = first hour with SepsisLabel = 1, plus 6 hours |
| Eligibility | Non-septic; uncertain onset (label already 1 in the first row: excluded from training and timing metrics, reviews reported separately); eligible septic (label turns on after the first row); fully observed (eligible, onset ≥ 12 h after first row) as a sensitivity denominator |
| Training target | 1 for hours T_onset − 12 ≤ h < T_onset; 0 otherwise; hours at/after onset removed from training |
| Splits | Per hospital, 70/15/15 train/val/test by patient, stratified on ever-septic, seed 2026 |
| Comparisons | A→A, B→B, A→B, B→A; external always compared with the home model on the same test patients |
| Cross-hospital variable rule | Drop a variable observed for < 1% of patients at one hospital but not the other (result: EtCO2). The stricter 1%-of-patient-hours version is reported in `outputs/availability.csv` |
| Feature sets | Values-only, missingness-only, combined (definitions in `src/features.py`) |
| Excluded fields | ICULOS, HospAdmTime, Unit1, Unit2 (shortcut ablation only) |
| Imputation | Within-patient carry-forward; stale after 6 h (vitals) or 24 h (labs); then a draw from the training hospital's observed values, indexed by a hash of (patient, hour, variable) |
| Model | LightGBM, binary objective, early stopping on validation log-loss (50 rounds, max 2,000) |
| Search | 6 configurations: num_leaves {15, 31, 63} × learning_rate {0.03, 0.06}; min_data_in_leaf 200, feature_fraction 0.8, lambda_l2 1, positive-class weight = negatives ÷ positives in training |
| Selection | Highest validation PR-AUC on the home hospital only |
| Logistic regression | Current carried-forward values plus age and sex, standardized, balanced class weights |
| Clinical rules | SIRS count and NEWS-inspired score on current values; missing values score 0; no consciousness field; NEWS treats FiO2 > 0.21 as supplemental oxygen (FiO2 > 1 read as percent) |
| Policy | k review slots per 12-hour shift, evenly spaced (offsets ⌊i·12/k⌋); 12-hour snooze after a review; ties broken at random |
| Primary budget | k = 3 per 20 beds (Tier 1: k = 1, 2, 5 for random-k, SIRS and LightGBM combined) |
| Primary metric | Share of eligible septic patients whose review came 6–12 hours before onset |
| Review classes | Early (0 < lead ≤ 12), early 6 h+ (6 ≤ lead ≤ 12), late (lead ≤ 0), false (non-septic or lead > 12), uncertain (uncertain-onset group) |
| Simulation | Full-cohort sweep, 20 beds, admission orders seeds 1–5; every test patient passes through once |
| Intervals | 200 patient-level bootstrap replicates (resample test patients, new admission order, all policies on the same replicate); 2.5th and 97.5th percentiles; paired differences inside each replicate |
| Failure cases | Miss: eligible septic patient never caught early by LightGBM combined at A→A with the most hours in its 12-hour window. False alert: patient with the most false reviews by LightGBM combined at A→A |
| Before-new-testing signal | First hour within 24 h before onset where lactate, WBC, pH or PaCO2 appears after ≥ 12 h unmeasured, or ≥ 2 labs are new in the same hour; frequency checked on training patients only before test results are opened |

## Deviations log

| When (Central) | Change | Reason |
| --- | --- | --- |
| Sat Nov 14, 00:31 | Validation rows get the same positive-class weight as training rows when computing the early-stopping log-loss | With weighted training and unweighted validation, validation log-loss rose from the first round (class weighting inflates predicted probabilities), so every LightGBM fit stopped after 1 round. No test-set result had been computed. Model selection is still by validation PR-AUC, which weighting does not affect |
| Sat Nov 14, 10:12 | Post-hoc version 2 (SOFA, 24 h trends, baseline changes, local adaptation) built and compared with version 1 on validation patients only | Asked whether the model could be improved after seeing version 1. Rule fixed beforehand: test version 2 only if it beats version 1 on the review-slot metric at both hospitals on validation. It did not (A +0.3, B −4.0 points), so version 2 was never run on the test set and version 1 stands. See docs/version2_attempt.md |
