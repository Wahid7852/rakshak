# Tests HR/lifecycle signal multipliers and their expiry.
from backend.engine.insider.lifecycle_store import DEFAULT_MULTIPLIER, LifecycleStore


def test_no_signal_is_default_multiplier():
    store = LifecycleStore()
    assert store.multiplier_for("EMP001") == DEFAULT_MULTIPLIER


def test_resignation_raises_multiplier():
    store = LifecycleStore()
    store.record("EMP001", "resignation_submitted", now=1000.0)
    assert store.multiplier_for("EMP001", now=1000.0) > DEFAULT_MULTIPLIER


def test_multiplier_expires_after_window():
    store = LifecycleStore()
    store.record("EMP001", "resignation_submitted", now=1000.0)
    still_active = store.multiplier_for("EMP001", now=1000.0 + 30 * 86400)
    expired = store.multiplier_for("EMP001", now=1000.0 + 50 * 86400)
    assert still_active > DEFAULT_MULTIPLIER
    assert expired == DEFAULT_MULTIPLIER


def test_role_change_has_no_multiplier():
    store = LifecycleStore()
    store.record("EMP001", "role_change", now=1000.0)
    assert store.multiplier_for("EMP001", now=1000.0) == DEFAULT_MULTIPLIER


def test_newer_signal_replaces_older_one():
    store = LifecycleStore()
    store.record("EMP001", "performance_improvement_plan", now=1000.0)
    pip_multiplier = store.multiplier_for("EMP001", now=1000.0)
    store.record("EMP001", "resignation_submitted", now=1000.0)
    resignation_multiplier = store.multiplier_for("EMP001", now=1000.0)
    assert resignation_multiplier > pip_multiplier


def test_employees_are_independent():
    store = LifecycleStore()
    store.record("EMP001", "resignation_submitted", now=1000.0)
    assert store.multiplier_for("EMP002", now=1000.0) == DEFAULT_MULTIPLIER
