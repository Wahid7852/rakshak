# Tests the InsiderDetector end to end: baseline -> anomaly -> risk -> Decision.
import pytest

from backend.engine.insider.alert_store import AlertStore
from backend.engine.insider.feedback_store import FeedbackStore
from backend.engine.insider.lifecycle_store import LifecycleStore
from backend.engine.insider.pipeline import InsiderDetector, InsiderHrSignalDetector

WEEKDAY_MORNING = "2026-06-{day:02d}T09:00:00Z"


def _login_event(employee_id: str, day: int, host: str = "WKS-001") -> dict:
    return {
        "employee_id": employee_id,
        "event_type": "login",
        "timestamp": WEEKDAY_MORNING.format(day=day),
        "host_id": host,
        "success": True,
    }


@pytest.mark.anyio
async def test_routine_logins_stay_benign(monkeypatch):
    store = AlertStore()
    monkeypatch.setattr("backend.engine.insider.pipeline.get_alert_store", lambda: store)
    detector = InsiderDetector("login", "insider_login_baseline")

    decision = None
    for day in range(1, 26):
        decision = await detector.score(_login_event("EMP001", day), {})

    assert decision.verdict == "benign"
    snap = store.snapshot("EMP001")
    assert snap.severity in ("low", "medium")


@pytest.mark.anyio
async def test_new_host_after_established_baseline_raises_risk(monkeypatch):
    store = AlertStore()
    monkeypatch.setattr("backend.engine.insider.pipeline.get_alert_store", lambda: store)
    detector = InsiderDetector("login", "insider_login_baseline")

    for day in range(1, 22):
        await detector.score(_login_event("EMP001", day, host="WKS-001"), {})
    before = store.snapshot("EMP001").risk

    await detector.score(_login_event("EMP001", 22, host="WKS-EXT-99"), {})
    after = store.snapshot("EMP001").risk

    assert after > before


@pytest.mark.anyio
async def test_unknown_employee_id_defaults_gracefully():
    detector = InsiderDetector("login", "insider_login_baseline")
    decision = await detector.score({"event_type": "login", "timestamp": "2026-06-01T09:00:00Z"}, {})
    assert decision.verdict in ("malicious", "benign")


@pytest.mark.anyio
async def test_employees_scored_independently(monkeypatch):
    store = AlertStore()
    monkeypatch.setattr("backend.engine.insider.pipeline.get_alert_store", lambda: store)
    detector = InsiderDetector("login", "insider_login_baseline")

    for day in range(1, 10):
        await detector.score(_login_event("EMP001", day), {})
    await detector.score(_login_event("EMP002", 1), {})

    assert store.snapshot("EMP001") is not None
    assert store.snapshot("EMP002") is not None
    assert store.snapshot("EMP001").employee_id != store.snapshot("EMP002").employee_id


@pytest.mark.anyio
async def test_hr_signal_detector_records_lifecycle_state(monkeypatch):
    lifecycle = LifecycleStore()
    monkeypatch.setattr("backend.engine.insider.pipeline.get_lifecycle_store", lambda: lifecycle)
    detector = InsiderHrSignalDetector()

    decision = await detector.score(
        {"employee_id": "EMP001", "event_type": "hr_signal", "signal_type": "resignation_submitted"}, {}
    )

    assert decision.score == 0.0  # informational only, not itself an anomaly score
    assert lifecycle.state_for("EMP001").signal_type == "resignation_submitted"


@pytest.mark.anyio
async def test_lifecycle_multiplier_alone_does_not_raise_risk(monkeypatch):
    """A resignation with zero anomalous behavior around it shouldn't produce
    risk on its own - the multiplier only matters when it's amplifying an
    actual contribution."""
    alert_store = AlertStore()
    lifecycle = LifecycleStore()
    monkeypatch.setattr("backend.engine.insider.pipeline.get_alert_store", lambda: alert_store)
    monkeypatch.setattr("backend.engine.insider.pipeline.get_lifecycle_store", lambda: lifecycle)
    lifecycle.record("EMP001", "resignation_submitted")  # defaults to real "now", matching score()'s own clock

    detector = InsiderDetector("login", "insider_login_baseline")
    for day in range(1, 26):
        await detector.score(_login_event("EMP001", day), {})

    snap = alert_store.snapshot("EMP001")
    assert snap.severity in ("low", "medium")


@pytest.mark.anyio
async def test_lifecycle_multiplier_amplifies_a_real_anomaly(monkeypatch):
    alert_store = AlertStore()
    lifecycle = LifecycleStore()
    monkeypatch.setattr("backend.engine.insider.pipeline.get_alert_store", lambda: alert_store)
    monkeypatch.setattr("backend.engine.insider.pipeline.get_lifecycle_store", lambda: lifecycle)

    detector = InsiderDetector("login", "insider_login_baseline")
    for day in range(1, 22):
        await detector.score(_login_event("EMP001", day, host="WKS-001"), {})
    baseline_risk = alert_store.snapshot("EMP001").risk

    lifecycle.record("EMP001", "resignation_submitted")  # defaults to real "now", matching score()'s own clock
    await detector.score(_login_event("EMP001", 22, host="WKS-EXT-99"), {})
    amplified_risk = alert_store.snapshot("EMP001").risk

    assert amplified_risk > baseline_risk
    assert any("departing" in r for r in alert_store.snapshot("EMP001").last_reasons)


@pytest.mark.anyio
async def test_analyst_dismissal_reduces_future_contribution_from_that_reason(monkeypatch):
    """Two employees with an identical new-host event at the same point in an
    identical history - one gets a prior false_positive dismissal on
    new_host, the other doesn't. The dismissed one's risk bump should be
    smaller, without the reason disappearing outright (never full silence)."""
    alert_store = AlertStore()
    feedback = FeedbackStore()
    monkeypatch.setattr("backend.engine.insider.pipeline.get_alert_store", lambda: alert_store)
    monkeypatch.setattr("backend.engine.insider.pipeline.get_feedback_store", lambda: feedback)

    detector_control = InsiderDetector("login", "insider_login_baseline")
    for day in range(1, 22):
        await detector_control.score(_login_event("EMP_CONTROL", day, host="WKS-001"), {})
    before_control = alert_store.snapshot("EMP_CONTROL").risk
    await detector_control.score(_login_event("EMP_CONTROL", 22, host="WKS-EXT-99"), {})
    control_bump = alert_store.snapshot("EMP_CONTROL").risk - before_control

    feedback.apply("EMP_DISMISSED", ["new_host"], "false_positive")
    detector_dismissed = InsiderDetector("login", "insider_login_baseline")
    for day in range(1, 22):
        await detector_dismissed.score(_login_event("EMP_DISMISSED", day, host="WKS-001"), {})
    before_dismissed = alert_store.snapshot("EMP_DISMISSED").risk
    await detector_dismissed.score(_login_event("EMP_DISMISSED", 22, host="WKS-EXT-99"), {})
    dismissed_bump = alert_store.snapshot("EMP_DISMISSED").risk - before_dismissed

    assert 0.0 < dismissed_bump < control_bump
