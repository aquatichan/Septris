import numpy as np
import pandas as pd

from src.familiarity import fit_familiarity_guard, summary

def test_guard_flags_clear_distribution_shift():
    rng = np.random.default_rng(0)
    train = pd.DataFrame(rng.normal(0, 1, size=(1000, 3)), columns=["hr", "map", "resp"])
    validation = pd.DataFrame(rng.normal(0, 1, size=(300, 3)), columns=train.columns)
    guard = fit_familiarity_guard(train, validation, quantile=0.01, validation_abstention_rate=0.05)
    shifted = pd.DataFrame(rng.normal(8, 1, size=(30, 3)), columns=train.columns)
    assert guard.unfamiliar(shifted).mean() > 0.95

def test_guard_report_is_bounded():
    x = pd.DataFrame({"a": [0., 1., 2.], "b": [0., 1., 2.]})
    guard = fit_familiarity_guard(x, x, quantile=0.1, validation_abstention_rate=0.5)
    report = summary(guard, x)
    assert 0 <= report["unfamiliar_share"] <= 1
    assert 0 <= report["median_out_of_range_share"] <= 1
