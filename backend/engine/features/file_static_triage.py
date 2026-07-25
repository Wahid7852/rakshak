# Extracts backend engine features for file static triage.

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any
from ...orchestrator.types import Decision
from ..utils.entropy import shannon_entropy

@dataclass
class Detector:
    name: str = "file_static"
    cost_ms_estimate: int = 5

    async def score(self, payload, context: Dict[str, Any]) -> Decision:
        b = payload if isinstance(payload, (bytes, bytearray)) else b""
        s = 0.0
        if b.startswith(b"MZ"):
            s += 0.2
        if shannon_entropy(b[:200 * 1024]) > 7.5:
            s += 0.3
        return Decision(min(1.0, s), 0.4, "malicious" if s >= 0.5 else "benign", self.name)
