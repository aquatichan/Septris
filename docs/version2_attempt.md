# Version 2 attempt (post hoc, validation only)

Built on Saturday 14 Nov 2026, after version 1's test results were seen.
To keep the test set clean, version 2 was compared with version 1 on
**validation patients only**, with a rule fixed in advance: run version 2 on
the test set only if it beats version 1 on the review-slot metric at both
hospitals. It did not, so **version 1 remains the result**, and no version 2
test-set number was computed.

## What version 2 added

`src/features_v2.py` (leakage-tested on 200 real patients) adds 70 columns on
top of version 1's combined set:

- a partial SOFA score from recorded values (platelets, bilirubin,
  creatinine, MAP, SpO2/FiO2), each component, and its rise over the last 24 h;
- 24-hour min/max/mean of vital signs and 24-hour max/min of six key labs;
- change from each patient's own first recorded value for 12 variables.

It also tried **local adaptation**: continuing to train each model on 1,000
training patients from the other hospital, then evaluating on that
hospital's validation patients.

## Validation results (never the test set)

Share of eligible sepsis patients reviewed 6–12 h before onset, 3 reviews
per 12-hour shift, mean of 5 admission orders. Hourly AUROC in brackets.

| Model | Hospital A validation | Hospital B validation |
| --- | --- | --- |
| Version 1, trained at A | 28.9% (0.789) | 19.4% (0.692) |
| Version 2, trained at A | 29.2% (0.795) | 20.8% (0.699) |
| Version 2, trained at A, adapted on 1,000 B patients | – | 20.1% (0.713) |
| Version 1, trained at B | 20.0% (0.703) | 27.2% (0.757) |
| Version 2, trained at B | 20.2% (0.730) | 23.2% (0.766) |
| Version 2, trained at B, adapted on 1,000 A patients | 21.2% (0.732) | – |
| Random review | 8.0% | 9.4% |

Version 2 nudged hourly AUROC up everywhere (by 0.006 to 0.027), but on the
decision that matters it was +0.3 points at A and −4.0 points at B. With
about 130 eligible septic validation patients per hospital, a few patients
either way move these numbers by several points, so none of the differences
is a reliable gain. Local adaptation added at most about one point.

## What this tells us

The richer summaries of the same hourly vitals and labs do not add usable
information. This matches the learning curve (half the training patients do
as well as all of them) and the perfect-information ceiling (about 90% of
cases could be reviewed in time under the same budget). The limit is what
the dataset records, not the model: there are no culture or antibiotic
orders, medications or notes, which are the signals that define and precede
recorded onset. Datasets that include them (MIMIC-IV, eICU-CRD, HiRID,
AmsterdamUMCdb, SICdb) all require credentialed access.

Reproduce: `python scripts/07_v2_train.py` (writes `outputs/v2/`).
