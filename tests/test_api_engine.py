import numpy as np

from api.engine import _logit


def test_logit_is_monotonic_and_finite_at_extremes():
    values = _logit(np.array([0.0, 0.1, 0.5, 0.9, 1.0]))
    assert np.all(np.isfinite(values))
    assert np.all(np.diff(values) > 0)
