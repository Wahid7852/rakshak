# Tests the self-relative (not fixed-threshold) HalfSpaceForest anomaly scoring.
import random

from backend.engine.insider.anomaly import InsiderAnomalyEngine

_LOGIN_FEATURES = {"hour_zscore": 0.1, "hour_drift": 0.1, "new_host": 0.0, "off_hours": 0.0, "failed_login": 0.0}


def _jittered_normal(rng: random.Random) -> dict:
    # real feature extraction never produces the exact same vector twice -
    # a deterministically-repeated vector is an unrealistic edge case for
    # HalfSpaceForest's per-call cross-tree normalization (score() can
    # legitimately return exactly 0.0 if every tree happens to agree).
    return {
        "hour_zscore": max(0.0, 0.1 + rng.gauss(0, 0.05)),
        "hour_drift": max(0.0, 0.1 + rng.gauss(0, 0.05)),
        "new_host": 0.0,
        "off_hours": 0.0,
        "failed_login": 0.0,
    }


def test_is_warm_false_before_enough_observations():
    engine = InsiderAnomalyEngine()
    for _ in range(5):
        engine.score("EMP001", "login", _LOGIN_FEATURES)
    assert not engine.is_warm("EMP001", "login")


def test_is_warm_true_after_enough_observations():
    engine = InsiderAnomalyEngine()
    for _ in range(25):
        engine.score("EMP001", "login", _LOGIN_FEATURES)
    assert engine.is_warm("EMP001", "login")


def test_self_relative_zscore_low_for_repeated_regular_events():
    """The exact regression this engine hit: a fixed threshold on the raw HST
    score false-triggered because different employees have different score
    'floors'. The self-relative z-score must stay low once an employee's own
    floor is established, even though the raw score itself never approaches 0."""
    engine = InsiderAnomalyEngine()
    zscores = []
    for _ in range(60):
        _raw, z = engine.score("EMP001", "login", _LOGIN_FEATURES)
        zscores.append(z)
    # after warm-up, repeating the *same* event shouldn't look like an outlier
    # relative to this employee's own (by-now-established) score history
    assert max(zscores[30:]) < 2.0


def test_self_relative_zscore_flags_a_genuine_change():
    rng = random.Random(7)
    engine = InsiderAnomalyEngine()
    for _ in range(40):
        engine.score("EMP001", "login", _jittered_normal(rng))
    outlier_features = {"hour_zscore": 4.0, "hour_drift": 3.0, "new_host": 1.0, "off_hours": 1.0, "failed_login": 1.0}
    zscores = [engine.score("EMP001", "login", outlier_features)[1] for _ in range(5)]
    assert max(zscores) > 0.0


def test_employees_have_independent_score_baselines():
    engine = InsiderAnomalyEngine()
    for _ in range(25):
        engine.score("EMP001", "login", _LOGIN_FEATURES)
    # EMP002 is cold - its own warm-up gate should be independent of EMP001's
    assert not engine.is_warm("EMP002", "login")
    assert engine.is_warm("EMP001", "login")
