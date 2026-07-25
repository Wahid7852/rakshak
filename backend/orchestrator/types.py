# Coordinates backend orchestration for types.
from dataclasses import dataclass
from typing import Literal


@dataclass
class Decision:
    score: float
    confidence: float
    verdict: Literal["malicious", "benign", "unknown"]
    used: str
