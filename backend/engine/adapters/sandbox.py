# Provides sandbox signal adapters for backend decisions.
from __future__ import annotations
import asyncio, os, shutil, tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class Signals(Protocol):
    """Structural contract shared by every signals type an adapter can return."""

    def as_context(self) -> dict[str, str]:
        ...


@dataclass(frozen=True)
class SandboxSignals:
    """Normalized sandbox signals consumed by the orchestrator."""

    bytes: int
    api_calls: int = 0
    signals: int = 0
    timed_out: bool = False
    backend: str = "static"

    def as_context(self) -> dict[str, str]:
        return {
            "sandbox_bytes": str(self.bytes),
            "sandbox_api_calls": str(self.api_calls),
            "sandbox_signals": str(self.signals),
            "sandbox_timed_out": str(int(self.timed_out)),
            "sandbox_backend": self.backend,
        }


class SandboxAdapter(Protocol):
    async def analyze(self, payload: bytes, timeout_s: float = 0.2) -> Signals:
        ...

    def close(self) -> None:
        ...


class StaticSandboxAdapter:
    """Safe local adapter that records payload metadata without executing it."""

    def __init__(self, workdir: str | os.PathLike[str] | None = None):
        self.workdir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="rk_sbx_"))
        self.workdir.mkdir(parents=True, exist_ok=True)

    async def analyze(self, payload: bytes, timeout_s: float = 0.2) -> SandboxSignals:
        sample = self.workdir / "sample.bin"
        sample.write_bytes(payload)
        await asyncio.sleep(min(max(timeout_s, 0.0), 0.2))

        size = sample.stat().st_size
        # Conservative signal: PE-looking bytes are interesting, but not a verdict.
        signals = 1 if payload.startswith(b"MZ") else 0
        return SandboxSignals(bytes=size, signals=signals, backend="static")

    def close(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)


class BwrapSandboxAdapter:
    """Real static-analysis adapter: runs the bwrap-isolated worker.

    Unlike StaticSandboxAdapter (which only records payload metadata), this
    delegates to backend.engine.sandbox.runner.run_sandboxed, which actually
    inspects the sample (entropy, format sniff, suspicious strings) inside a
    bwrap jail. registry.py's file_sandbox_signal detector reads those exact
    keys, so this is the adapter production traffic should get.
    """

    def __init__(self, workdir: str | os.PathLike[str] | None = None):
        self.workdir = workdir

    async def analyze(self, payload: bytes, timeout_s: float = 0.2) -> "RawSandboxSignals":
        from backend.engine.sandbox.runner import run_sandboxed

        raw = await run_sandboxed(payload, timeout_s=timeout_s)
        return RawSandboxSignals(raw)

    def close(self) -> None:
        pass


@dataclass(frozen=True)
class RawSandboxSignals:
    """Wraps run_sandboxed's dict so it satisfies the SandboxAdapter.analyze() contract."""

    raw: dict

    def as_context(self) -> dict[str, str]:
        from backend.engine.sandbox.runner import sandbox_context

        return sandbox_context(self.raw)


class DynamicSandboxAdapter:
    """Real dynamic/behavioral adapter: actually EXECUTES the sample.

    A materially different risk class than BwrapSandboxAdapter (which only
    reads bytes, never executes). Delegates to
    backend.engine.sandbox.dynamic_runner.run_dynamic - see that module's
    docstring for the isolation model and its limits before enabling this
    anywhere. Only handles ELF; non-ELF payloads (e.g. Windows PE) get a
    same-shaped "not executed" result, not a crash. Never the default -
    must be explicitly selected via RAKSHAK_SANDBOX_ADAPTER=dynamic.
    """

    def __init__(self, workdir: str | os.PathLike[str] | None = None):
        self.workdir = workdir

    async def analyze(self, payload: bytes, timeout_s: float = 5.0) -> "RawDynamicSignals":
        from backend.engine.sandbox.dynamic_runner import run_dynamic

        raw = await run_dynamic(payload, timeout_s=timeout_s)
        return RawDynamicSignals(raw)

    def close(self) -> None:
        pass


@dataclass(frozen=True)
class RawDynamicSignals:
    """Wraps run_dynamic's dict so it satisfies the SandboxAdapter.analyze() contract.

    Uses a "dynamic_" key prefix, distinct from BwrapSandboxAdapter's
    "sandbox_" prefix - registry.py's file_sandbox_signal detector reads
    static sandbox_* keys specifically and shouldn't be handed dynamic
    signals it wasn't designed to score.
    """

    raw: dict

    def as_context(self) -> dict[str, str]:
        from backend.engine.sandbox.dynamic_runner import dynamic_context

        return dynamic_context(self.raw)


class CapeSandboxAdapter:
    """Deliberately unimplemented integration boundary for CAPE Sandbox.

    This is a scope decision, not an in-progress feature: RAKSHAK's dynamic analysis
    needs are covered by DynamicSandboxAdapter for ELF, and Windows PE stays static-only
    (see pe_features.py) rather than adding a VM-based detonation service. Nothing here
    submits, polls, or parses CAPE reports, and nothing is planned to. Kept only so
    RAKSHAK_SANDBOX_ADAPTER=cape fails with a clear explanation instead of either
    silently doing nothing or crashing somewhere unrelated.
    """

    def __init__(self, api_url: str | None = None, api_token: str | None = None):
        self.api_url = api_url or os.getenv("RAKSHAK_CAPE_API_URL", "")
        self.api_token = api_token or os.getenv("RAKSHAK_CAPE_API_TOKEN", "")

    async def analyze(self, payload: bytes, timeout_s: float = 0.2) -> SandboxSignals:
        raise NotImplementedError(
            "RAKSHAK_SANDBOX_ADAPTER=cape is not supported. CAPE integration was "
            "deliberately not built (see backend/engine/adapters/sandbox.py's "
            "CapeSandboxAdapter docstring for why) - use 'bwrap' for static analysis "
            "or 'dynamic' for real ELF execution instead."
        )

    def close(self) -> None:
        return None


def create_sandbox_adapter(kind: str | None = None, workdir: str | os.PathLike[str] | None = None) -> SandboxAdapter:
    selected = (kind if kind is not None else os.getenv("RAKSHAK_SANDBOX_ADAPTER", "bwrap")).lower()
    if selected == "bwrap":
        return BwrapSandboxAdapter(workdir=workdir)
    if selected in {"static", "fake", "none"}:
        return StaticSandboxAdapter(workdir=workdir)
    if selected == "dynamic":
        return DynamicSandboxAdapter(workdir=workdir)
    if selected == "cape":
        return CapeSandboxAdapter()
    raise ValueError(f"Unsupported sandbox adapter: {selected}")
