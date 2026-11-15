# LightGBM vs the temporal GRU, and the Septris mix (post hoc)

> This project is a prototype and is not medical advice.

**Bottom line.** Miheer's masked temporal GRU (a deep-learning model that
reads each patient's hours in order) and our LightGBM catch about the same
number of sepsis patients at home, but **they catch different patients**,
and the GRU holds up better at a hospital it has never seen. Septris now uses
both: each bed gets the **higher** of the two models' 0–100 risks
("whichever is more worried"). That rule was chosen on validation patients
only. On test patients it is the best of the three at ranking hours and on
the official Challenge score in all four train→test pairs, and it ties the
GRU on the review-slot metric. None of the differences between the three
models on the review-slot metric are large enough to rule out chance.

The pre-registered version 1 result (LightGBM, 3 reviews per shift) is
unchanged; everything here is post hoc and logged in
[preregistration.md](preregistration.md).

## How the mix was chosen

`scripts/10_blend.py` turns each model's score into a percentile of its home
hospital's validation hours, then scores 8 candidates on **validation
patients only** (both hospitals, 3 and 5 reviews per shift, 5 admission
orders): each model alone, three weighted averages, the higher of the two
("max"), and two ways of taking turns by review slot.

| Candidate | Mean validation catch share |
| --- | ---: |
| LightGBM alone | 32.5% |
| GRU alone | 33.9% |
| Averages (75/25, 50/50, 25/75) | 32.2–33.3% |
| **Max (chosen)** | **33.9%** |
| Taking turns | 32.8–33.7% |

The first version of the rule only had the averages and picked the GRU
alone. After the test comparison below showed that the two models catch
different patients, "max" and "taking turns" were added and the rule was
re-run, still on validation only. Max edged the GRU by 0.06 points, which is
a tie in practice.

## Test results (caught 6–12 h before onset, % of eligible septic patients)

Mean of 5 admission orders; 95% intervals from 200 patient-level bootstrap
replicates are in `outputs/results/results_table.csv`.

| Reviews per shift | Tested on | LightGBM | GRU | **Septris mix** | SIRS | Random |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 3 | A, trained at A | 25.1 | 26.1 | **25.6** | 12.5 | 8.0 |
| 3 | A, trained at B | 15.5 | 21.5 | **20.8** | | |
| 3 | B, trained at B | 26.3 | 29.6 | **29.1** | 16.9 | 9.3 |
| 3 | B, trained at A | 23.7 | 26.3 | **25.4** | | |
| 5 | A, trained at A | 32.9 | 33.4 | **33.1** | 17.9 | 15.6 |
| 5 | A, trained at B | 24.9 | 28.1 | **28.8** | | |
| 5 | B, trained at B | 35.1 | 36.0 | **37.2** | 20.9 | 13.7 |
| 5 | B, trained at A | 30.3 | 30.4 | **32.2** | | |

Paired differences (mix minus LightGBM, mix minus GRU) all have 95%
intervals that include 0. The biggest single gain is moving to a new
hospital: at Hospital A with the B-trained model, the mix catches 5.2 points
more than LightGBM at 3 reviews per shift (−0.4 to +10.6).

**Hourly ranking (AUROC, test hours):**

| Train → test | LightGBM | GRU | Mix |
| --- | ---: | ---: | ---: |
| A → A | 0.776 | 0.781 | **0.793** |
| B → A | 0.669 | 0.691 | **0.708** |
| A → B | 0.747 | 0.737 | **0.761** |
| B → B | 0.784 | 0.790 | **0.804** |

**Official PhysioNet 2019 utility** (threshold chosen on home validation):
A→A 0.354 / 0.370 / **0.381**, A→B 0.192 / 0.199 / **0.227**, B→A 0.163 /
0.193 / **0.213**, B→B 0.275 / 0.276 / **0.296** (LightGBM / GRU / mix).

## Where each model wins

From `scripts/11_compare_models.py` (same bed schedules; means over 5
admission orders).

**They catch different patients.** At Hospital A with home models and 3
reviews per shift: about 30 patients are caught only by LightGBM, 33 only by
the GRU, and 29 by both. If one review could follow both models, about 92 of
238 patients would be caught, but the review budget is fixed, so the mix
catches about 61. Overlap is lowest when moving to a new hospital (B-trained
at A: 25 LightGBM only, 39 GRU only, 12 both).

**The GRU is better for long stays.** At 5 reviews per shift, for patients
whose sepsis was recorded more than 72 hours after arrival, the GRU catches
54–58% (LightGBM 34–52%). It reads the whole stay in order, while LightGBM
only sees summaries of the last 6 hours. LightGBM wins for sepsis recorded
24–72 hours in, in 2 of 4 settings (A→A 32% vs 25%, A→B 22% vs 11%), and
for sepsis in the first 24 hours when the B-trained models are moved to A
(22% vs 8%).

**The GRU transfers better.** Moved from B to A, LightGBM's hourly AUROC
falls to 0.669 and the GRU's to 0.691. Like LightGBM, the GRU sees which
tests were done, so it is not free of the measurement-pattern effect
described in [results.md](results.md).

## What this does not show

- Gains over LightGBM are small and not statistically clear on the
  review-slot metric; the clearer gains are in hourly ranking and utility.
- The mix was chosen after seeing that the single models catch different
  patients on test data, so its test numbers are post hoc. The weight itself
  came from validation patients only.
- The same limits as version 1 apply: retrospective data, two hospital
  systems, and onset partly defined by clinician orders.

Reproduce: `python scripts/08_temporal_gru.py && python scripts/10_blend.py
&& python scripts/03_evaluate.py && python scripts/11_compare_models.py`.

## Update: 3-seed GRU and Miheer's later candidates

Two more validation-only checks were run after the sections above were
written; the test tables above predate them.

1. **GRU seed ensemble.** Two more GRU seeds were trained with the same
   recipe, and the three seeds' validation percentiles averaged. Inside the
   mix this raised the mean validation catch share from 33.9% to 35.2%, so
   the ensemble replaced the single GRU. Test results for the mix now: 5
   reviews per shift, 33.2% (A) and 37.6% (B) at home, 26.1% and 31.9% at
   the unseen hospital; 3 reviews per shift, 26.2% (A) and 30.9% (B).
2. **Queue-tuned LightGBM and Platt blend (Miheer).** `scripts/15_final_mix.py`
   compared 10 combinations on validation patients. max(LightGBM, GRU
   ensemble) stayed best at 35.2%; swapping in the queue-tuned LightGBM gave
   34.4%, the highest of all three 35.1%, the Platt blend 33.6%. The mix was
   therefore left unchanged. For information, at 3 reviews per shift on test
   patients the Platt blend scores 26.6% (A→A), 31.6% (B→B), 22.6% (B→A) and
   24.0% (A→B), against the mix's 26.2%, 30.9%, 21.8% and 24.6%: within
   about a point either way, well inside the bootstrap intervals.

The practical reading: several sensible ways of combining a tree model with
a sequence model land within a point of each other, and all of them beat
either model's weak spot (LightGBM at an unseen hospital).
