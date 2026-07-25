# Tests per-employee baseline warm-up and z-score behavior.
import random

from backend.engine.insider.entity_state import (
    EmployeeBaseline,
    EntityBaselineStore,
    RunningStat,
    SLOW_EWMA_ALPHA,
    WARMUP_MIN_OBSERVATIONS,
    drift_ratio,
    drift_zscore,
)


def test_running_stat_cold_start_not_warmed_up():
    stat = RunningStat()
    for _ in range(WARMUP_MIN_OBSERVATIONS - 1):
        stat.update(1.0)
    assert not stat.warmed_up


def test_running_stat_warms_up_after_min_observations():
    stat = RunningStat()
    for _ in range(WARMUP_MIN_OBSERVATIONS):
        stat.update(1.0)
    assert stat.warmed_up


def test_running_stat_zscore_flags_outlier_after_stable_history():
    stat = RunningStat()
    for _ in range(40):
        stat.update(1.0)  # perfectly stable baseline
    assert abs(stat.zscore(1.0)) < 0.5
    assert stat.zscore(50.0) > 5.0


def test_entity_baseline_store_creates_lazily_and_persists():
    store = EntityBaselineStore()
    a = store.get("EMP001")
    a.known_hosts.add("WKS-001")
    b = store.get("EMP001")
    assert b is a
    assert "WKS-001" in b.known_hosts
    assert store.get("EMP002") is not a


def test_stat_uses_given_alpha_only_on_first_creation():
    store = EntityBaselineStore()
    baseline = store.get("EMP001")
    fast = baseline.stat("v")
    slow = baseline.stat("v:slow", alpha=SLOW_EWMA_ALPHA)
    assert fast.alpha != slow.alpha
    # a second call with a different alpha doesn't recreate/reset it
    same_slow = baseline.stat("v:slow", alpha=0.9)
    assert same_slow is slow
    assert same_slow.alpha == SLOW_EWMA_ALPHA


def test_drift_zscore_near_zero_for_stationary_process():
    rng = random.Random(1)
    fast, slow = RunningStat(), RunningStat(alpha=SLOW_EWMA_ALPHA)
    drifts = []
    for _ in range(150):
        x = rng.gauss(9.0, 0.4)
        if slow.warmed_up:
            drifts.append(abs(drift_zscore(fast, slow)))
        fast.update(x)
        slow.update(x)
    assert max(drifts) < 1.5


def test_drift_ratio_rises_for_a_climbing_series():
    fast, slow = RunningStat(), RunningStat(alpha=SLOW_EWMA_ALPHA)
    for _ in range(20):
        fast.update(100.0)
        slow.update(100.0)
    ratios = []
    for i in range(20):
        x = 100.0 * (1.05**i)  # steady climb
        ratios.append(drift_ratio(fast, slow))
        fast.update(x)
        slow.update(x)
    assert ratios[-1] > ratios[0]
    assert ratios[-1] > 0.2  # fast has meaningfully outpaced slow by the end


def test_drift_ratio_zero_for_identical_baselines():
    fast, slow = RunningStat(), RunningStat(alpha=SLOW_EWMA_ALPHA)
    for _ in range(20):
        fast.update(500.0)
        slow.update(500.0)
    assert abs(drift_ratio(fast, slow)) < 0.05


def test_windowed_sum_includes_only_values_within_the_window():
    baseline = EmployeeBaseline(employee_id="EMP001")
    day = 86400.0
    total = baseline.windowed_sum("blast", ts=1 * day, value=100.0, window_days=14)
    assert total == 100.0
    total = baseline.windowed_sum("blast", ts=10 * day, value=200.0, window_days=14)
    assert total == 300.0  # both within the trailing 14 days
    total = baseline.windowed_sum("blast", ts=30 * day, value=50.0, window_days=14)
    assert total == 50.0  # the first two events are now outside the window


def test_windowed_sum_keys_are_independent():
    baseline = EmployeeBaseline(employee_id="EMP001")
    baseline.windowed_sum("a", ts=0.0, value=100.0, window_days=14)
    total_b = baseline.windowed_sum("b", ts=0.0, value=5.0, window_days=14)
    assert total_b == 5.0
