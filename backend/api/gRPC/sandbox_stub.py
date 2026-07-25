# Implements gRPC backend support for the sandbox stub.
from __future__ import annotations

from typing import Any, Dict

from backend.engine.sandbox.runner import run_sandboxed


class Sandbox:
    """Read-only static analysis, isolated with bwrap. Never executes the sample.

    Kept as a thin wrapper (rather than calling run_sandboxed directly) so
    callers hold an object with a lifecycle (`close()`), matching the
    streaming-upload call sites in decider_server.py.
    """

    def __init__(self, workdir=None):
        # workdir kept for backwards-compat call sites; the sandboxed worker
        # manages its own private scratch dir per run.
        self.workdir = workdir

    async def run(self, payload: bytes, timeout_s: float = 5.0) -> Dict[str, Any]:
        return await run_sandboxed(payload, timeout_s=timeout_s)

    def close(self) -> None:
        pass
