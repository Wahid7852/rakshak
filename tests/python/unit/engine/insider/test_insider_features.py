# Tests per-employee feature extraction relative to each employee's own baseline.
from datetime import datetime, timedelta, timezone

from backend.engine.insider.entity_state import EmployeeBaseline
from backend.engine.insider.features import (
    data_transfer_features,
    file_access_features,
    login_features,
)

_BASE_DAY = datetime(2026, 6, 1, 9, 0, 0, tzinfo=timezone.utc)


def _weekday_morning(day: int) -> str:
    dt = _BASE_DAY + timedelta(days=day - 1)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


OFF_HOURS = "2026-06-15T02:00:00Z"


def _login_event(day: int, host: str = "WKS-001", success: bool = True) -> dict:
    return {
        "employee_id": "EMP001",
        "event_type": "login",
        "timestamp": _weekday_morning(day),
        "host_id": host,
        "success": success,
    }


def test_login_first_ever_host_is_not_flagged_new():
    baseline = EmployeeBaseline(employee_id="EMP001")
    features = login_features(_login_event(1), baseline)
    assert features["new_host"] == 0.0


def test_login_new_host_flagged_after_baseline_established():
    baseline = EmployeeBaseline(employee_id="EMP001")
    for day in range(1, 5):
        login_features(_login_event(day, host="WKS-001"), baseline)
    features = login_features(_login_event(5, host="WKS-999"), baseline)
    assert features["new_host"] == 1.0


def test_login_off_hours_flag():
    baseline = EmployeeBaseline(employee_id="EMP001")
    event = {**_login_event(1), "timestamp": OFF_HOURS}
    features = login_features(event, baseline)
    assert features["off_hours"] == 1.0


def test_login_failed_flag():
    baseline = EmployeeBaseline(employee_id="EMP001")
    features = login_features(_login_event(1, success=False), baseline)
    assert features["failed_login"] == 1.0


def test_login_hour_zscore_requires_warmup():
    baseline = EmployeeBaseline(employee_id="EMP001")
    features = login_features(_login_event(1), baseline)
    assert features["warmed_up"] == 0.0
    assert features["hour_zscore"] == 0.0


def _file_event(day: int, path: str, sensitivity: str = "internal", size: int = 200_000) -> dict:
    return {
        "employee_id": "EMP001",
        "event_type": "file_access",
        "timestamp": _weekday_morning(day),
        "path": path,
        "sensitivity": sensitivity,
        "bytes": size,
    }


def test_file_access_first_ever_path_is_not_flagged_new():
    baseline = EmployeeBaseline(employee_id="EMP001")
    features = file_access_features(_file_event(1, "/shares/a.txt"), baseline)
    assert features["new_path"] == 0.0


def test_file_access_new_path_flagged_after_baseline_established():
    baseline = EmployeeBaseline(employee_id="EMP001")
    for day in range(1, 5):
        file_access_features(_file_event(day, "/shares/a.txt"), baseline)
    features = file_access_features(_file_event(5, "/shares/never_before.txt"), baseline)
    assert features["new_path"] == 1.0


def test_file_access_volume_outlier_detected_after_stable_baseline():
    baseline = EmployeeBaseline(employee_id="EMP001")
    for day in range(1, 25):
        file_access_features(_file_event(day, "/shares/a.txt", sensitivity="internal", size=200_000), baseline)
    features = file_access_features(
        _file_event(25, "/shares/a.txt", sensitivity="internal", size=20_000_000), baseline
    )
    assert features["volume_zscore"] > 2.5


def test_file_access_sensitivity_tiers_have_independent_baselines():
    """A rare access to a 'restricted' file shouldn't inherit the (unrelated)
    volume baseline built from routine 'public' file access."""
    baseline = EmployeeBaseline(employee_id="EMP001")
    for day in range(1, 25):
        file_access_features(_file_event(day, "/shares/public.txt", sensitivity="public", size=50_000), baseline)
    # the public tier is warmed up, the restricted tier has never been seen
    features = file_access_features(
        _file_event(25, "/shares/restricted.txt", sensitivity="restricted", size=50_000), baseline
    )
    assert features["volume_zscore"] == 0.0  # restricted tier isn't warmed up yet, not flagged


def _transfer_event(day: int, destination: str = "internal-fileshare", size: int = 300_000) -> dict:
    return {
        "employee_id": "EMP001",
        "event_type": "data_transfer",
        "timestamp": _weekday_morning(day),
        "destination": destination,
        "bytes": size,
    }


def test_data_transfer_new_destination_flagged_after_baseline_established():
    baseline = EmployeeBaseline(employee_id="EMP001")
    for day in range(1, 5):
        data_transfer_features(_transfer_event(day), baseline)
    features = data_transfer_features(_transfer_event(5, destination="personal-gdrive"), baseline)
    assert features["new_destination"] == 1.0


def test_data_transfer_staged_trend_catches_rising_weekly_volume():
    baseline = EmployeeBaseline(employee_id="EMP001")
    day = 1
    for _ in range(25):
        data_transfer_features(_transfer_event(day, size=300_000), baseline)
        day += 1
    # individually-unremarkable transfers that are collectively much larger
    # than this employee's normal trailing-week sum
    features = None
    for _ in range(10):
        features = data_transfer_features(_transfer_event(day, size=900_000), baseline)
        day += 1
    assert features["staged_trend"] > 0.0


def test_data_transfer_blast_radius_accumulates_within_window():
    baseline = EmployeeBaseline(employee_id="EMP001")
    f1 = data_transfer_features(_transfer_event(1, size=1_000_000), baseline)
    f2 = data_transfer_features(_transfer_event(2, size=1_000_000), baseline)
    assert f2["blast_radius_bytes"] == f1["blast_radius_bytes"] + 1_000_000


def test_file_access_blast_radius_weights_by_sensitivity():
    baseline_public = EmployeeBaseline(employee_id="EMP_PUBLIC")
    baseline_restricted = EmployeeBaseline(employee_id="EMP_RESTRICTED")
    f_public = file_access_features(_file_event(1, "/a.txt", sensitivity="public", size=100_000), baseline_public)
    f_restricted = file_access_features(
        _file_event(1, "/a.txt", sensitivity="restricted", size=100_000), baseline_restricted
    )
    # same raw bytes, but restricted-tier access should count for more
    assert f_restricted["blast_radius_bytes"] > f_public["blast_radius_bytes"]
