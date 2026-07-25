# Defines stable HTTP API request and response schemas.
from typing import Literal

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


class InsiderEventIn(BaseModel):
    """One collector-agent event. Fields beyond employee_id/event_type/timestamp
    are optional because they vary by subtype (see backend/engine/insider/features.py
    for which ones each subtype actually reads)."""

    employee_id: str = Field(..., min_length=1, max_length=128)
    event_type: Literal["login", "file_access", "data_transfer", "hr_signal"]
    timestamp: str
    host_id: str | None = None
    src_ip: str | None = None
    success: bool | None = None
    method: str | None = None
    path: str | None = None
    sensitivity: str | None = None
    action: str | None = None
    destination: str | None = None
    channel: str | None = None
    bytes: int | None = Field(default=None, ge=0)
    signal_type: Literal[
        "resignation_submitted", "offboarding_scheduled", "performance_improvement_plan", "role_change"
    ] | None = None


class InsiderIngestRequest(BaseModel):
    events: list[InsiderEventIn] = Field(..., min_length=1, max_length=500)


class InsiderIngestResponse(BaseModel):
    accepted: int
    rejected: int = 0


class InsiderAlertOut(BaseModel):
    alert_id: int
    employee_id: str
    subtype: str
    severity: str
    risk: float = Field(..., ge=0.0, le=1.0)
    reasons: list[str]
    timestamp: float
    feedback: str | None = None


class InsiderAlertsResponse(BaseModel):
    alerts: list[InsiderAlertOut]


class InsiderUserOut(BaseModel):
    employee_id: str
    risk: float = Field(..., ge=0.0, le=1.0)
    severity: str
    last_subtype: str
    last_reasons: list[str]
    last_seen: float
    narrative: str
    blast_radius_bytes: float = 0.0
    eta_critical_days: float | None = None


class InsiderFeedbackRequest(BaseModel):
    verdict: Literal["confirmed", "false_positive"]
    note: str | None = Field(default=None, max_length=1000)


class InsiderFeedbackResponse(BaseModel):
    ok: bool
    alert_id: int
    employee_id: str
    damped_reason_keys: list[str]
