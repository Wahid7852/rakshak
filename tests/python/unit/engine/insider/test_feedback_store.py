# Tests analyst feedback damping and its floor/reset behavior.
from backend.engine.insider.feedback_store import FLOOR_MULTIPLIER, FeedbackStore

DEFAULT = 1.0


def test_no_feedback_is_default_multiplier():
    store = FeedbackStore()
    assert store.multiplier_for("EMP001", "new_host") == DEFAULT


def test_false_positive_halves_multiplier():
    store = FeedbackStore()
    store.apply("EMP001", ["new_host"], "false_positive")
    assert store.multiplier_for("EMP001", "new_host") == DEFAULT * 0.5


def test_repeated_false_positives_approach_but_never_reach_zero():
    store = FeedbackStore()
    for _ in range(10):
        store.apply("EMP001", ["new_host"], "false_positive")
    multiplier = store.multiplier_for("EMP001", "new_host")
    assert multiplier == FLOOR_MULTIPLIER
    assert multiplier > 0.0


def test_confirmed_resets_to_default():
    store = FeedbackStore()
    store.apply("EMP001", ["new_host"], "false_positive")
    store.apply("EMP001", ["new_host"], "confirmed")
    assert store.multiplier_for("EMP001", "new_host") == DEFAULT


def test_damping_is_scoped_per_employee_and_reason_key():
    store = FeedbackStore()
    store.apply("EMP001", ["new_host"], "false_positive")
    assert store.multiplier_for("EMP002", "new_host") == DEFAULT  # different employee
    assert store.multiplier_for("EMP001", "off_hours") == DEFAULT  # different reason


def test_apply_affects_all_given_keys():
    store = FeedbackStore()
    store.apply("EMP001", ["new_host", "off_hours"], "false_positive")
    assert store.multiplier_for("EMP001", "new_host") < DEFAULT
    assert store.multiplier_for("EMP001", "off_hours") < DEFAULT
