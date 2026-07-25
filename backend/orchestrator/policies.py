# Coordinates backend orchestration for policies.
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Budgets:
    LOG_MS: int = 5              # per log event (target p95)
    FILE_INIT_MS: int = 50       # early file decision
    FILE_TOTAL_MS: int = 250     # total incl. sandbox enrich


@dataclass(frozen=True)
class Thresholds:
    MALICIOUS: float = 0.75
    BENIGN: float = 0.25
    BORDERLINE_LOW: float = 0.45
    BORDERLINE_HIGH: float = 0.65
