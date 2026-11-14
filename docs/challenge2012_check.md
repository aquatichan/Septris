# Third-hospital deterioration check: PhysioNet 2012 (exploratory, post hoc)

> This project is a prototype and is not medical advice.

**Bottom line:** at a third hospital, the frozen version 1 Septris model
was never trained on these patients and never trained to predict death. Even
so, it ranks the 14.2% of patients who die in hospital about as well as
established ICU severity scores, and better than SIRS and NEWS. The
measurement-pattern-only model is again the least portable.

## Data

[PhysioNet/CinC Challenge 2012](https://physionet.org/content/challenge-2012/1.0.0/)
(open access, ODC-By 1.0): 12,000 adult ICU stays (sets A, B, C), first 48
hours, with in-hospital death, SOFA and SAPS-I for every stay. Downloaded from
PhysioNet by the team on 14 Nov 2026. SHA-256 of the files used:

| File | SHA-256 |
| --- | --- |
| set-a.tar.gz | 8cb250f179cd0952b4b9ebcf8954b63d70383131670fac1cfee13deaa13ca920 |
| set-b.tar.gz | b1637a2a423a8e76f8f087896cfc5fdf28f88519e1f4e874fbda69b2a64dac30 |
| set-c.tar.gz | a4a56b95bcee4d50a3874fe298bf2998f2ed0dd98a676579573dc10419329ee1 |
| Outcomes-a.txt | 2613ea60ccda29f87571a7d6b09ad130858a8ccd66325bd073365925026883c2 |
| Outcomes-b.txt | 1305f29734da374a809483229a99f33a9230aa8d4fa74b1a2d6ad788136423d5 |
| Outcomes-c.txt | 0b32dcb7753c0f18f2f5fde498a28618b8879c5e527ce0dae8ad120dd7e205c9 |

Converted to the 2019 hourly format (hours 0–47; arterial blood pressure
where recorded, non-invasive otherwise). The 2012 data has no pulse-oximetry
SpO2 and fewer labs, so those columns stay unmeasured.

## Question and method

The question here is not sepsis, because the data has no sepsis label. It is
narrower: does each frozen model's highest score in the first 24 or 48 hours
rank patients who later die in hospital above those who survive? SOFA and
SAPS-I are the dataset's own first-24-hour severity scores; they are a
benchmark here, not a fair head-to-head, because they use GCS, urine output
and ventilation, which our models never see.

## Results (AUROC for in-hospital death, 12,000 stays)

| Score | First 24 h | First 48 h |
| --- | --- | --- |
| SAPS-I (dataset field, 24 h) | 0.660 | – |
| SOFA (dataset field, 24 h) | 0.638 | – |
| Septris combined, trained at B | 0.631 | 0.657 |
| Septris combined, trained at A | 0.602 | 0.633 |
| Values-only, trained at B | 0.634 | 0.653 |
| Values-only, trained at A | 0.601 | 0.612 |
| NEWS-inspired | 0.591 | 0.608 |
| SIRS | 0.584 | 0.588 |
| Measurement-pattern only, trained at B | 0.581 | 0.587 |
| Measurement-pattern only, trained at A | 0.489 | 0.516 |

## What this adds

- Septris's score tracks general deterioration at a hospital it has
  never seen, about as well as purpose-built severity scores.
- For the third time (B→A, eICU, this check), the measurement-pattern model
  is the least portable, while physiology carries over.
- This is not evidence of early sepsis warning: death is a different outcome
  and the window is a stay's first two days.

Reproduce: `python scripts/09_challenge2012_check.py --data data/raw/challenge2012`
(place the six PhysioNet files there first).
