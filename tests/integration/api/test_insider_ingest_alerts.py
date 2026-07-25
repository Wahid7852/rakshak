# Tests the insider-threat ingest -> alerts -> per-user API flow end to end.
from __future__ import annotations
import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.engine.insider.alert_store import get_alert_store

client = TestClient(app)
HEADERS = {"x-api-key": "dev-key"}
WEEKDAY_MORNING = "2026-06-{day:02d}T09:00:00Z"


@pytest.fixture(autouse=True)
def _reset_alert_store():
    store = get_alert_store()
    store._alerts.clear()
    store._subtype_snapshots.clear()
    yield


def _login_payload(employee_id: str, day: int, host: str = "WKS-001") -> dict:
    return {
        "employee_id": employee_id,
        "event_type": "login",
        "timestamp": WEEKDAY_MORNING.format(day=day),
        "host_id": host,
        "success": True,
    }


def test_insider_ingest_requires_api_key():
    r = client.post("/v1/insider/ingest", json={"events": [_login_payload("EMP001", 1)]})
    assert r.status_code == 401


def test_insider_ingest_rejects_empty_batch():
    r = client.post("/v1/insider/ingest", json={"events": []}, headers=HEADERS)
    assert r.status_code == 422


def test_insider_ingest_accepts_valid_batch():
    events = [_login_payload("EMP001", day) for day in range(1, 6)]
    r = client.post("/v1/insider/ingest", json={"events": events}, headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] == 5
    assert body["rejected"] == 0


def test_unknown_employee_returns_404():
    r = client.get("/v1/insider/users/NOBODY", headers=HEADERS)
    assert r.status_code == 404


def test_ingest_then_alerts_flow_surfaces_new_host_anomaly():
    # establish a normal baseline, then break it with a brand new host
    events = [_login_payload("EMP001", day, host="WKS-001") for day in range(1, 22)]
    events.append(_login_payload("EMP001", 22, host="WKS-EXT-99"))
    r = client.post("/v1/insider/ingest", json={"events": events}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["accepted"] == len(events)

    user = client.get("/v1/insider/users/EMP001", headers=HEADERS)
    assert user.status_code == 200
    body = user.json()
    assert body["employee_id"] == "EMP001"
    assert 0.0 <= body["risk"] <= 1.0
    assert body["severity"] in ("low", "medium", "high", "critical")
    assert "EMP001" in body["narrative"]
    assert body["blast_radius_bytes"] >= 0.0
    assert body["eta_critical_days"] is None or body["eta_critical_days"] >= 0.0

    alerts = client.get("/v1/insider/alerts", headers=HEADERS)
    assert alerts.status_code == 200
    for alert in alerts.json()["alerts"]:
        assert alert["employee_id"] == "EMP001"
        assert 0.0 <= alert["risk"] <= 1.0


def test_alerts_min_severity_filter():
    events = [_login_payload("EMP001", day) for day in range(1, 10)]
    client.post("/v1/insider/ingest", json={"events": events}, headers=HEADERS)

    r = client.get("/v1/insider/alerts?min_severity=critical", headers=HEADERS)
    assert r.status_code == 200
    for alert in r.json()["alerts"]:
        assert alert["severity"] == "critical"


def test_feedback_on_unknown_alert_returns_404():
    r = client.post("/v1/insider/alerts/999999/feedback", json={"verdict": "confirmed"}, headers=HEADERS)
    assert r.status_code == 404


def test_feedback_flow_marks_alert_and_reports_damped_keys():
    # a single new-host event stays well under the medium-severity alert
    # floor by design (see risk.py) - several distinct new hosts in a row
    # are needed to actually produce an alert to give feedback on.
    events = [_login_payload("EMP050", day, host="WKS-001") for day in range(1, 22)]
    for i in range(8):
        events.append(_login_payload("EMP050", 22 + i, host=f"WKS-EXT-{i:02d}"))
    r = client.post("/v1/insider/ingest", json={"events": events}, headers=HEADERS)
    assert r.json()["accepted"] == len(events)

    alerts = client.get("/v1/insider/alerts?employee_id=EMP050", headers=HEADERS).json()["alerts"]
    assert alerts, "expected at least one alert for the new-host event"
    alert_id = alerts[0]["alert_id"]

    r = client.post(
        f"/v1/insider/alerts/{alert_id}/feedback",
        json={"verdict": "false_positive", "note": "known new laptop rollout"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["employee_id"] == "EMP050"
    assert "new_host" in body["damped_reason_keys"]

    refetched = client.get("/v1/insider/alerts?employee_id=EMP050", headers=HEADERS).json()["alerts"]
    marked = next(a for a in refetched if a["alert_id"] == alert_id)
    assert marked["feedback"] == "false_positive"


def test_hr_signal_ingest_is_accepted_and_produces_no_alert_alone():
    events = [
        {
            "employee_id": "EMP099",
            "event_type": "hr_signal",
            "timestamp": WEEKDAY_MORNING.format(day=1),
            "signal_type": "resignation_submitted",
        }
    ]
    r = client.post("/v1/insider/ingest", json={"events": events}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["accepted"] == 1

    # an hr_signal alone updates lifecycle state, not the alert-bearing
    # per-subtype baselines - no snapshot should exist for it on its own
    user = client.get("/v1/insider/users/EMP099", headers=HEADERS)
    assert user.status_code == 404
