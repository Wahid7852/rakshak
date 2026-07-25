# Defines stable HTTP API request and response schemas.
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    version: str


class LogScanRequest(BaseModel):
    line: str = Field(..., min_length=1, max_length=65536)


class LogScanResponse(BaseModel):
    suspicious: bool
    score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    model: str
    reason: str


class FileScanResponse(BaseModel):
    malicious: bool
    score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    model: str
    reason: str
    sha256: str
    quarantined: bool = False
    quarantine_id: str | None = None


class QuarantineEntryResponse(BaseModel):
    quarantine_id: str
    original_path: str
    quarantine_file: str
    reason: str
    sha256: str
    timestamp: float


class QuarantineListResponse(BaseModel):
    entries: list[QuarantineEntryResponse]


class QuarantineRestoreRequest(BaseModel):
    quarantine_id: str
    dest_path: str | None = None


class QuarantineActionResponse(BaseModel):
    ok: bool
    quarantine_id: str
