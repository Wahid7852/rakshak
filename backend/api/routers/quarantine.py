# Defines REST access to the quarantine store: list, restore, delete.
import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request

from backend.api import deps
from backend.api.schemas import (
    QuarantineActionResponse,
    QuarantineListResponse,
    QuarantineRestoreRequest,
)
from backend.observability.metrics import track_request

from ..security.rate_limit import limiter, quarantine_mutate_rate

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/quarantine", response_model=QuarantineListResponse)
async def list_quarantine(request: Request):
    with track_request("http", "/v1/quarantine") as outcome:
        entries = deps.get_quarantine_manager().list_quarantined()
        outcome["status"] = "200"
        return {"entries": [asdict(e) for e in entries]}


@router.post("/quarantine/restore", response_model=QuarantineActionResponse)
@limiter.limit(quarantine_mutate_rate)
async def restore_quarantine(request: Request, body: QuarantineRestoreRequest):
    with track_request("http", "/v1/quarantine/restore") as outcome:
        ok = deps.get_quarantine_manager().restore_file(body.quarantine_id, body.dest_path)
        if not ok:
            outcome["status"] = "404"
            raise HTTPException(status_code=404, detail="quarantine id not found or restore failed")
        outcome["status"] = "200"
        return {"ok": True, "quarantine_id": body.quarantine_id}


@router.delete("/quarantine/{quarantine_id}", response_model=QuarantineActionResponse)
@limiter.limit(quarantine_mutate_rate)
async def delete_quarantine(request: Request, quarantine_id: str):
    with track_request("http", "/v1/quarantine/{quarantine_id}") as outcome:
        ok = deps.get_quarantine_manager().remove_file(quarantine_id)
        if not ok:
            outcome["status"] = "404"
            raise HTTPException(status_code=404, detail="quarantine id not found")
        outcome["status"] = "200"
        return {"ok": True, "quarantine_id": quarantine_id}
