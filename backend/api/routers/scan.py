# Defines bounded file-upload scanning for the HTTP API.
import logging, tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from backend.api import deps
from backend.api.config import settings
from backend.api.schemas import FileScanResponse
from backend.engine.sandbox.runner import run_sandboxed, sandbox_context
from backend.engine.utils.hashing import sha256_bytes
from backend.observability.metrics import record_quarantine, record_verdict, track_request
from backend.orchestrator.decision import Event, Router

from ..security.rate_limit import limiter, scan_file_rate

logger = logging.getLogger(__name__)

READ_CHUNK_BYTES = 1024 * 1024
MAX_FILE_BYTES = settings.max_file_bytes
router = APIRouter()
router_runtime = Router()

SANDBOX_TIMEOUT_S = 5.0
# matches Router.decide()'s own confidence bar for a definitive verdict
QUARANTINE_CONFIDENCE_MIN = 0.5


def _maybe_quarantine(content: bytes, filename: str, score: float) -> tuple[bool, str | None]:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, prefix="rk_scan_", suffix=".bin") as f:
            f.write(content)
            tmp_path = Path(f.name)
        entry = deps.get_quarantine_manager().quarantine_file(
            tmp_path, reason=f"malicious scan, client filename={filename!r}, score={score:.3f}"
        )
        if entry is None:
            return False, None
        return True, entry.quarantine_id
    except Exception:
        logger.exception("quarantine attempt failed for %s", filename)
        return False, None
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


async def _read_upload(file: UploadFile) -> bytes:
    content = bytearray()
    while chunk := await file.read(READ_CHUNK_BYTES):
        content.extend(chunk)
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"file exceeds {MAX_FILE_BYTES} byte limit",
            )
    if not content:
        raise HTTPException(status_code=400, detail="file payload is empty")
    return bytes(content)


@router.post("/scan/file", response_model=FileScanResponse)
@limiter.limit(scan_file_rate)
async def scan_file(request: Request, file: UploadFile = File(...)):
    with track_request("http", "/v1/scan/file") as outcome:
        try:
            content = await _read_upload(file)
            sbx_signals = await run_sandboxed(content, timeout_s=SANDBOX_TIMEOUT_S)
            context = {"path": file.filename or "", **sandbox_context(sbx_signals)}
            decision = await router_runtime.decide(
                Event(kind="file", payload=content, context=context)
            )
            record_verdict("file", decision.verdict)

            quarantined = False
            quarantine_id = None
            if decision.verdict == "malicious" and decision.confidence >= QUARANTINE_CONFIDENCE_MIN:
                quarantined, quarantine_id = _maybe_quarantine(content, file.filename or "unknown", decision.score)
                if quarantined:
                    record_quarantine()

            outcome["status"] = "200"
            return {
                "malicious": decision.verdict == "malicious",
                "score": decision.score,
                "confidence": decision.confidence,
                "model": decision.used,
                "reason": "orchestrator/router",
                "sha256": sha256_bytes(content).hex(),
                "quarantined": quarantined,
                "quarantine_id": quarantine_id,
            }
        except HTTPException as exc:
            outcome["status"] = str(exc.status_code)
            raise
        except Exception as exc:
            outcome["status"] = "500"
            logger.exception("scan_file failed")
            raise HTTPException(status_code=500, detail="internal error processing file") from exc
