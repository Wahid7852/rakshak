# Tests risk decay, severity buckets, and the low-false-positive escalation rule.
from backend.engine.insider.risk import RiskTracker, eta_critical_days


def test_single_modest_event_does_not_reach_high():
    tracker = RiskTracker()
    state = tracker.update("EMP001", contribution=0.2, reasons=["one flag"], now=1000.0)
    assert tracker.severity_for(state.risk) in ("low", "medium")


def test_risk_decays_over_time_without_new_events():
    tracker = RiskTracker()
    tracker.update("EMP001", contribution=0.5, reasons=["x"], now=1000.0)
    later = tracker.update("EMP001", contribution=0.0, reasons=[], now=1000.0 + 3 * 24 * 3600)
    assert later.risk < 0.3  # ~half-life has passed


def test_sustained_contributions_reach_critical():
    tracker = RiskTracker()
    state = None
    for i in range(10):
        # same day, i.e. real elapsed time is small relative to the decay half-life
        state = tracker.update("EMP001", contribution=0.2, reasons=["repeated signal"], now=1000.0 + i)
    assert tracker.severity_for(state.risk) == "critical"


def test_risk_is_capped_at_one():
    tracker = RiskTracker()
    state = tracker.update("EMP001", contribution=5.0, reasons=["x"], now=1000.0)
    assert state.risk == 1.0


def test_severity_thresholds_are_monotonic():
    tracker = RiskTracker()
    assert tracker.severity_for(0.0) == "low"
    assert tracker.severity_for(0.39) == "low"
    assert tracker.severity_for(0.40) == "medium"
    assert tracker.severity_for(0.65) == "high"
    assert tracker.severity_for(0.85) == "critical"


def test_employees_are_tracked_independently():
    tracker = RiskTracker()
    tracker.update("EMP001", contribution=0.9, reasons=["x"], now=1000.0)
    other = tracker.update("EMP002", contribution=0.0, reasons=[], now=1000.0)
    assert other.risk == 0.0


def test_eta_is_none_without_event_time_history():
    tracker = RiskTracker()
    state = tracker.update("EMP001", contribution=0.2, reasons=["x"], now=1000.0)
    assert eta_critical_days(state) is None  # no event_time given, no rate to project from


def test_eta_is_none_when_already_critical():
    tracker = RiskTracker()
    day = 86400.0
    state = None
    for i in range(5):
        state = tracker.update(
            "EMP001", contribution=0.3, reasons=["x"], now=1000.0 + i, event_time=i * day
        )
    assert state.risk >= 0.85
    assert eta_critical_days(state) is None


def test_eta_shrinks_as_risk_climbs_at_a_steady_rate():
    tracker = RiskTracker()
    day = 86400.0
    etas = []
    for i in range(6):
        state = tracker.update(
            "EMP001", contribution=0.05, reasons=["x"], now=1000.0 + i, event_time=i * day
        )
        eta = eta_critical_days(state)
        if eta is not None:
            etas.append(eta)
    assert len(etas) >= 2
    assert etas[-1] < etas[0]  # closer to critical each day at a steady contribution rate


def test_eta_is_none_when_rate_is_flat():
    tracker = RiskTracker()
    state = tracker.update("EMP001", contribution=0.1, reasons=["x"], now=1000.0, event_time=0.0)
    assert eta_critical_days(state) is None  # only one event_time sample, no rate yet


def test_eta_is_none_rather_than_an_absurdly_large_number():
    """A near-zero-but-positive rate is technically correct arithmetic for a
    huge projection (millions of days) - that's a real regression this
    engine hit, and it's useless to show anyone. Should report None instead."""
    tracker = RiskTracker()
    day = 86400.0
    state = tracker.update("EMP001", contribution=0.30, reasons=["x"], now=1000.0, event_time=0.0)
    state = tracker.update("EMP001", contribution=0.00001, reasons=[], now=1000.0, event_time=1 * day)
    eta = eta_critical_days(state)
    assert eta is None or eta < 365.0
