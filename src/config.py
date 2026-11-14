"""Frozen settings from the v3 project brief's pre-registration table.

Changing anything here after the first external test result must be logged
in docs/preregistration.md with the reason and time.
"""

SEED = 2026                      # patient splits
SIM_SEEDS = (1, 2, 3, 4, 5)      # admission orders for the full-cohort sweep
N_BOOT = 200                     # patient-level bootstrap replicates

TARGET_HOURS = 12                # train on "onset within the next 12 hours"
LABEL_LEAD_HOURS = 6             # official SepsisLabel turns on 6 h before onset

VITAL_STALE_HOURS = 6            # carried-forward vital becomes stale after 6 h
LAB_STALE_HOURS = 24             # carried-forward lab becomes stale after 24 h
ROLL_HOURS = 6                   # rolling min/max/mean window for vitals

BEDS = 20
SHIFT_HOURS = 12
PRIMARY_K = 3
TIER1_BUDGETS = (1, 2, 5)
SNOOZE_HOURS = 12                # no repeat review within 12 hours

RARE_PCT = 1.0                   # cross-hospital availability rule threshold

LGBM_SEARCH = [
    {"num_leaves": nl, "learning_rate": lr}
    for nl in (15, 31, 63) for lr in (0.03, 0.06)
]  # 6 configs (brief allows at most 8)
LGBM_FIXED = {
    "objective": "binary",
    "min_data_in_leaf": 200,
    "feature_fraction": 0.8,
    "lambda_l2": 1.0,
    "verbose": -1,
    "num_threads": 2,
    "seed": SEED,
}
MAX_ROUNDS = 2000
EARLY_STOP = 50

HOSPITALS = ("A", "B")
PAIRS = (("A", "A"), ("B", "B"), ("A", "B"), ("B", "A"))  # (train, test)
DISCLAIMER = "This project is a prototype and is not medical advice."
