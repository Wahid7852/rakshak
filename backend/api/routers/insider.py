# Defines backend API routes for insider-threat ingestion and alerts.
import logging
from typing import Dict

from fastapi import APIRouter, HTTPException, Query, Request

from backend.api.schemas import (
    InsiderAlertOut,
    InsiderAlertsResponse,
    InsiderFeedbackRequest,
    InsiderFeedbackResponse,
    InsiderIngestRequest,
    InsiderIngestResponse,
    InsiderUserOut,
)
from backend.engine.insider.alert_store import get_alert_store
from backend.engine.insider.feedback_store import get_feedback_store
from backend.engine.insider.narrative import build_narrative
from backend.observability.metrics import record_verdict, track_request
from backend.orchestrator.decision import ArtifactKind, Event, Router

from ..security.rate_limit import insider_ingest_rate, limiter

logger = logging.getLogger(__name__)

router = APIRouter()
router_runtime = Router()

# Maps the collector agent's event_type field to the orchestrator ArtifactKind
# that routes to the matching per-subtype baseline detector (decision.py).
_KIND_FOR_EVENT_TYPE: Dict[str, ArtifactKind] = {
    "login": "insider_login",
    "file_access": "insider_file_access",
    "data_transfer": "insider_transfer",
    "hr_signal": "insider_hr_signal",
}


@router.post("/insider/ingest", response_model=InsiderIngestResponse)
@limiter.limit(insider_ingest_rate)
async def insider_ingest(request: Request, req: InsiderIngestRequest):
    with track_request("http", "/v1/insider/ingest") as outcome:
        accepted = 0
        rejected = 0
        for event in req.events:
            kind = _KIND_FOR_EVENT_TYPE[event.event_type]
            payload = event.model_dump(exclude_none=True)
            try:
                decision = await router_runtime.decide(Event(kind=kind, payload=payload, context={}))
                record_verdict(kind, decision.verdict)
                accepted += 1
            except Exception:
                rejected += 1
                logger.exception(
                    "insider_ingest failed for employee_id=%s event_type=%s",
                    event.employee_id,
                    event.event_type,
                )
        outcome["status"] = "200"
        return {"accepted": accepted, "rejected": rejected}


@router.get("/insider/alerts", response_model=InsiderAlertsResponse)
async def insider_alerts(
    min_severity: str | None = Query(default=None),
    employee_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
):
    store = get_alert_store()
    alerts = store.alerts(min_severity=min_severity, employee_id=employee_id, limit=limit)
    return {
        "alerts": [
            InsiderAlertOut(
                alert_id=a.alert_id,
                employee_id=a.employee_id,
                subtype=a.subtype,
                severity=a.severity,
                risk=a.risk,
                reasons=a.reasons,
                timestamp=a.timestamp,
                feedback=a.feedback,
            )
            for a in alerts
        ]
    }


@router.post("/insider/alerts/{alert_id}/feedback", response_model=InsiderFeedbackResponse)
async def insider_alert_feedback(alert_id: int, req: InsiderFeedbackRequest):
    alert = get_alert_store().get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="no such alert_id")

    get_feedback_store().apply(alert.employee_id, alert.reason_keys, req.verdict)
    alert.feedback = req.verdict
    return InsiderFeedbackResponse(
        ok=True, alert_id=alert.alert_id, employee_id=alert.employee_id, damped_reason_keys=alert.reason_keys
    )


@router.get("/insider/users/{employee_id}", response_model=InsiderUserOut)
async def insider_user(employee_id: str):
    snap = get_alert_store().snapshot(employee_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="no data for this employee_id yet")
    narrative = build_narrative(
        snap.employee_id,
        snap.severity,
        snap.risk,
        snap.last_subtype,
        snap.recent_signals,
        blast_radius_bytes=snap.blast_radius_bytes,
        eta_critical_days=snap.eta_critical_days,
    )
    return InsiderUserOut(
        employee_id=snap.employee_id,
        risk=snap.risk,
        severity=snap.severity,
        last_subtype=snap.last_subtype,
        last_reasons=snap.last_reasons,
        last_seen=snap.last_seen,
        narrative=narrative,
        blast_radius_bytes=snap.blast_radius_bytes,
        eta_critical_days=snap.eta_critical_days,
    )
