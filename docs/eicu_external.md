# Third hospital system: eICU demo (exploratory, post hoc)

> This project is a prototype and is not medical advice.

**Bottom line: inconclusive for early warning.** The frozen version 1 models
ran on a third hospital system without any retraining. Under our
approximate onset label they did no better than random review, but that
label left only 52 usable sepsis cases and agrees poorly with recorded
diagnoses, so this test cannot say much about early warning. A check that
does not depend on our label shows the models still recognize sepsis
patients there about as well as NEWS, and that the measurement-pattern model
transfers worst, which matches the main result.

## Data

[eICU Collaborative Research Database demo v2.0.1](https://physionet.org/content/eicu-crd-demo/2.0.1/)
(open access, ODbL 1.0): 2,520 ICU stays from 186 US hospitals, 2014–2015.
The files came from a public GitHub copy (`shajoezhu/demo-eicu`). The 28
tables used here match PhysioNet's published SHA-256 checksums exactly; the
3 that differ (admission diagnoses, allergies, custom labs) are not used.

Converted to the Challenge's hourly format (scripts/08_eicu_external.py):
hourly medians from ICU admission; arterial blood pressure where recorded,
non-invasive otherwise; nurse-charted temperature; the Challenge's lab
columns mapped by name; stays with at least 8 ICU hours, capped at 14 days
(2,262 stays). Coverage of each variable is close to Hospitals A and B
(`outputs/eicu/coverage.csv`).

## Label (an approximation, fixed before scoring)

The demo has only 342 culture records, so the Challenge's "antibiotic plus
culture" suspicion of infection cannot be reproduced. We used: first
systemic antibiotic order (not cancelled; cefazolin excluded as surgical
prophylaxis) as suspicion; SOFA (platelets, bilirubin, creatinine,
MAP/vasopressors, PaO2/FiO2, GCS) rising by 2 or more within the Challenge's
window; onset = earlier of the two.

| Label check | Value |
| --- | --- |
| Stays labelled septic | 283 of 2,262 (12.5%) |
| Uncertain onset (already labelled at ICU hour 0) | 231 |
| **Eligible septic (usable for timing metrics)** | **52** |
| Labelled septic stays that also have a recorded sepsis diagnosis | 27% |
| Diagnosed sepsis stays that our label also marks | 28% |

Most eICU patients got their first antibiotic before reaching the ICU (in the
emergency department or on the ward), so onset falls at or before ICU
admission and no 6-hour warning is possible. That leaves 52 eligible cases,
too few for tight intervals.

## Results (zero-shot, frozen version 1 models)

3 reviews per 20-bed, 12-hour shift; mean of 5 admission orders; 95%
intervals from 200 patient-level bootstrap replicates.

| Policy | Caught 6–12 h early (of 52) | Hourly AUROC |
| --- | --- | --- |
| Random review | 8.1% (0.0–15.8) | – |
| SIRS | 8.8% (2.1–17.9) | 0.564 |
| NEWS-inspired | 11.2% (3.8–21.1) | 0.578 |
| LightGBM values-only, trained at A | 11.5% (2.1–17.9) | 0.545 |
| LightGBM values-only, trained at B | 10.4% (3.8–22.2) | 0.577 |
| Septris (combined), trained at A | 7.7% (0.0–14.3) | 0.518 |
| Septris (combined), trained at B | 7.3% (0.0–16.2) | 0.515 |
| Measurement-pattern only, trained at A | 7.7% (0.0–14.3) | 0.518 |
| Measurement-pattern only, trained at B | 5.4% (1.9–15.8) | 0.514 |

No policy's difference from random review has an interval that excludes 0
(`outputs/eicu/paired_differences.csv`).

## Label-free check

Ranking stays by their highest score in the first 24 ICU hours, against
whether the stay has a recorded sepsis diagnosis (276 of 2,262 stays):

| Model (trained at A) | Stay-level AUROC |
| --- | --- |
| NEWS-inspired | 0.691 |
| SIRS | 0.688 |
| Septris (combined) | 0.681 |
| Values-only | 0.677 |
| Measurement-pattern only | 0.568 |

## What this adds

- It supports the main finding: the measurement-pattern signal is the least
  portable. At a third system it is close to chance on both checks, while
  values-only and simple vital-sign scores keep some signal.
- It does not test early warning well: the label is approximate and leaves
  52 cases. A proper test needs the full eICU or MIMIC-IV with culture data
  (credentialed access).

Reproduce: `python scripts/08_eicu_external.py --eicu <demo>/data` and
`python scripts/08b_eicu_label_free.py <demo>/data`.
