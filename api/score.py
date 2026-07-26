# Vercel serverless entry point for the "run it live" demo: takes a batch of
# insider-threat events and scores them with the real backend.engine.insider
# code, not a client-side approximation. See site/demo/ for the caller and
# site/README.md for why this is scoped to one request instead of a fully
# persistent deployment (Vercel functions don't hold state between calls).
from __future__ import annotations

import asyncio
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engine.insider.pipeline import InsiderDetector, InsiderHrSignalDetector  # noqa: E402
from backend.engine.insider.narrative import build_narrative  # noqa: E402
import backend.engine.insider.alert_store as alert_store_mod  # noqa: E402
import backend.engine.insider.feedback_store as feedback_store_mod  # noqa: E402
import backend.engine.insider.lifecycle_store as lifecycle_store_mod  # noqa: E402

MAX_EVENTS = 3000  # ~0.2s to score 1300 events locally, plenty of headroom below any function timeout
MAX_EMPLOYEES = 40  # demo sanity limit, keeps one request's CPU time bounded
_VALID_EVENT_TYPES = {"login", "file_access", "data_transfer", "hr_signal"}
_KIND_FOR_EVENT_TYPE = {
    "login": "insider_login_baseline",
    "file_access": "insider_file_baseline",
    "data_transfer": "insider_transfer_baseline",
}


def _fresh_global_stores() -> None:
    # alert_store/feedback_store/lifecycle_store are module-level singletons
    # (see get_alert_store() etc.) so that the 3 per-subtype InsiderDetector
    # instances and the HR detector can share state within one ingest run -
    # exactly what the real backend wants across many requests from one
    # deployment. A public multi-tenant demo function is the opposite case:
    # every request is a different, unrelated visitor, and a warm Vercel
    # instance can serve several of them in a row. Resetting here is what
    # keeps one visitor's batch from leaking into another's results.
    alert_store_mod._default_store = alert_store_mod.AlertStore()
    feedback_store_mod._default_store = feedback_store_mod.FeedbackStore()
    lifecycle_store_mod._default_store = lifecycle_store_mod.LifecycleStore()


def _validate(events: object) -> tuple[list, str | None]:
    if not isinstance(events, list):
        return [], "events must be a list"
    if len(events) == 0:
        return [], "events must not be empty"
    if len(events) > MAX_EVENTS:
        return [], f"at most {MAX_EVENTS} events per request"

    seen_employees: set[str] = set()
    for e in events:
        if not isinstance(e, dict):
            return [], "each event must be an object"
        emp = e.get("employee_id")
        if not isinstance(emp, str) or not (1 <= len(emp) <= 128):
            return [], "employee_id must be a 1-128 character string"
        seen_employees.add(emp)
        if len(seen_employees) > MAX_EMPLOYEES:
            return [], f"at most {MAX_EMPLOYEES} distinct employee_id values per request"
        if e.get("event_type") not in _VALID_EVENT_TYPES:
            return [], "event_type must be one of login/file_access/data_transfer/hr_signal"
        if not isinstance(e.get("timestamp"), str):
            return [], "timestamp must be an ISO-8601 string"
    return events, None


def _process(events: list) -> dict:
    _fresh_global_stores()

    detectors = {
        "login": InsiderDetector("login", "insider_login_baseline"),
        "file_access": InsiderDetector("file_access", "insider_file_baseline"),
        "data_transfer": InsiderDetector("data_transfer", "insider_transfer_baseline"),
    }
    hr_detector = InsiderHrSignalDetector()

    accepted, rejected = 0, 0
    for event in sorted(events, key=lambda e: e.get("timestamp", "")):
        event_type = event.get("event_type")
        try:
            if event_type == "hr_signal":
                asyncio.run(hr_detector.score(event, {}))
            else:
                asyncio.run(detectors[event_type].score(event, {}))
            accepted += 1
        except Exception:
            rejected += 1

    store = alert_store_mod.get_alert_store()
    employees = []
    for snap in store.all_snapshots():
        narrative = build_narrative(
            snap.employee_id,
            snap.severity,
            snap.risk,
            snap.last_subtype,
            snap.recent_signals,
            blast_radius_bytes=snap.blast_radius_bytes,
            eta_critical_days=snap.eta_critical_days,
        )
        employees.append(
            {
                "id": snap.employee_id,
                "risk": round(snap.risk, 3),
                "sev": snap.severity,
                "subtype": snap.last_subtype,
                "narrative": narrative,
                "blast": snap.blast_radius_bytes,
                "eta": snap.eta_critical_days,
            }
        )

    return {"employees": employees, "accepted": accepted, "rejected": rejected}


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if length <= 0 or length > 2_000_000:  # 2MB sanity ceiling
            self._send_json(400, {"error": "missing or oversized request body"})
            return

        raw = self.rfile.read(length)
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON"})
            return

        events, err = _validate(body.get("events") if isinstance(body, dict) else None)
        if err:
            self._send_json(400, {"error": err})
            return

        try:
            result = _process(events)
        except Exception as exc:  # last-resort guard, never leak a stack trace to the client
            self._send_json(500, {"error": f"scoring failed: {exc.__class__.__name__}"})
            return

        self._send_json(200, result)

    def do_GET(self) -> None:
        self._send_json(200, {"ok": True, "usage": "POST {\"events\": [...]} to score a batch live"})
