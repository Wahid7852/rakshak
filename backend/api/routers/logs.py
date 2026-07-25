# Defines backend API routes for logs.
import logging

from fastapi import APIRouter, HTTPException, Request

from backend.api.schemas import LogScanRequest, LogScanResponse
from backend.observability.metrics import record_verdict, track_request
from backend.orchestrator.decision import Event, Router

from ..security.rate_limit import limiter, scan_logline_rate

logger = logging.getLogger(__name__)

router = APIRouter()
router_runtime = Router()

@router.post("/scan/logline", response_model=LogScanResponse)
@limiter.limit(scan_logline_rate)
async def scan_logline(request: Request, req: LogScanRequest):
    with track_request("http", "/v1/scan/logline") as outcome:
        try:
            decision = await router_runtime.decide(Event(kind="log", payload=req.line, context={}))
            record_verdict("log", decision.verdict)
            outcome["status"] = "200"
            return {
                "suspicious": decision.verdict == "malicious",
                "score": decision.score,
                "confidence": decision.confidence,
                "model": decision.used,
                "reason": "orchestrator/router",
            }
        except Exception:
            outcome["status"] = "500"
            logger.exception("scan_logline failed")
            raise HTTPException(status_code=500, detail="internal error processing log line")
