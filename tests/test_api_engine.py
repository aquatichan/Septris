import numpy as np

from api.engine import _logit


def test_logit_is_monotonic_and_finite_at_extremes():
    values = _logit(np.array([0.0, 0.1, 0.5, 0.9, 1.0]))
    assert np.all(np.isfinite(values))
    assert np.all(np.diff(values) > 0)


def test_feature_patient_id_is_accepted_by_the_feature_code():
    """Any API patient id must map to an id the feature code can parse.

    Regression: the engine used the literal id "inference_patient", which
    src.features cannot parse, so every scoring call raised ValueError.
    """
    from api.engine import FrozenLightGBMEngine as E
    from src.features import _pid_int
    import pandas as pd

    assert E._feature_patient_id([{"patient_id": "p000123"}]) == "p000123"  # dataset ids pass through
    for pid in ("MRN-88.1", "inference_patient", "a", ""):
        mapped = E._feature_patient_id([{"patient_id": pid}])
        assert mapped == E._feature_patient_id([{"patient_id": pid}])  # stable
        _pid_int(pd.Series([mapped]))  # parses without error
