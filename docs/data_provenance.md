# Data provenance

**Dataset:** PhysioNet/Computing in Cardiology Challenge 2019, *Early
Prediction of Sepsis from Clinical Data*, version 1.0.0, training sets A and
B. Licence: Creative Commons Attribution 4.0 International (CC BY 4.0).
DOI: [10.13026/v64v-d857](https://doi.org/10.13026/v64v-d857).

## How the files used here were obtained

The build environment could not download from physionet.org directly (its
network blocks that host). The 40,336 patient files were therefore taken
from a public GitHub mirror of the training data
(`MartinOravecSvK/Early-Prediction-of-Sepsis`, folders `Dataset/training_setA`
and `Dataset/training_setB`) and verified against PhysioNet's own file
listing, read live from
`https://physionet.org/files/challenge-2019/1.0.0/training/training_set{A,B}/`
on 14 Nov 2026:

| Check | Set A | Set B |
| --- | --- | --- |
| Patient files on PhysioNet | 20,336 | 20,000 |
| Patient files in the mirror | 20,336 | 20,000 |
| Total bytes, PhysioNet listing | 131,388,704 | 123,668,780 |
| Total bytes, mirror | 131,388,704 | 123,668,780 |
| Fingerprint of every (file name, byte size) pair | identical | identical |

Every file name and every individual file size matches. Anyone with
PhysioNet access can reproduce from the official source with
`python scripts/01_audit.py --download`, which uses the standard
`wget -r -N -c -np` pattern on the PhysioNet URL.

## Required citations

1. Reyna MA, Josef C, Jeter R, Shashikumar SP, Moody B, Westover MB,
   Sharma A, Nemati S, Clifford GD. *Early Prediction of Sepsis from
   Clinical Data: The PhysioNet/Computing in Cardiology Challenge 2019*
   (version 1.0.0). PhysioNet (2019). https://doi.org/10.13026/v64v-d857
2. Reyna MA, Josef CS, Jeter R, Shashikumar SP, Westover MB, Nemati S,
   Clifford GD, Sharma A. Early Prediction of Sepsis From Clinical Data: The
   PhysioNet/Computing in Cardiology Challenge 2019. *Critical Care Medicine*
   48(2):210–217 (2020). https://doi.org/10.1097/CCM.0000000000004145
3. PhysioNet standard citation, as listed on the dataset page.

The official Challenge scoring code is vendored unchanged in
`vendor/physionet_2019_evaluation/` under its BSD 2-Clause licence.

## What is shipped in this repository

No raw patient files are committed. `app/artifacts/` holds a derived subset
for the demo (priority scores, a few vital signs and two labs for Hospital A
test patients, plus review logs), which CC BY 4.0 permits with attribution.
