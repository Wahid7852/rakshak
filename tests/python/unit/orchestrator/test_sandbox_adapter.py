# Tests sandbox adapter signal normalization.
from unittest.mock import AsyncMock, patch

import pytest

from backend.api.gRPC.sandbox_stub import Sandbox
from backend.engine.adapters.sandbox import (
    BwrapSandboxAdapter,
    CapeSandboxAdapter,
    StaticSandboxAdapter,
    create_sandbox_adapter,
)


@pytest.mark.anyio
async def test_static_sandbox_adapter_returns_context(tmp_path):
    adapter = StaticSandboxAdapter(workdir=tmp_path)

    signals = await adapter.analyze(b"MZpayload", timeout_s=0)

    assert signals.bytes == 9
    assert signals.signals == 1
    assert signals.as_context()["sandbox_backend"] == "static"
    adapter.close()


@pytest.mark.anyio
async def test_bwrap_sandbox_adapter_wraps_run_sandboxed():
    # mock run_sandboxed - a unit test shouldn't spawn a real bwrap subprocess
    raw = {
        "bytes": 9,
        "sha256": "deadbeef",
        "entropy": 7.9,
        "format": "pe",
        "suspicious_strings": ["powershell"],
        "timed_out": False,
    }
    adapter = BwrapSandboxAdapter()
    with patch(
        "backend.engine.sandbox.runner.run_sandboxed", new=AsyncMock(return_value=raw)
    ):
        signals = await adapter.analyze(b"MZpayload", timeout_s=0.2)

    context = signals.as_context()
    # these are exactly the keys registry.py's _SandboxSignal detector reads
    assert context["sandbox_bytes"] == "9"
    assert context["sandbox_entropy"] == "7.9"
    assert context["sandbox_format"] == "pe"
    assert context["sandbox_suspicious_strings"] == "['powershell']"
    assert context["sandbox_timed_out"] == "False"
    adapter.close()


def test_sandbox_factory_defaults_to_bwrap(monkeypatch):
    monkeypatch.delenv("RAKSHAK_SANDBOX_ADAPTER", raising=False)

    assert isinstance(create_sandbox_adapter(), BwrapSandboxAdapter)


def test_sandbox_factory_rejects_unknown_adapter():
    with pytest.raises(ValueError):
        create_sandbox_adapter("unknown")


@pytest.mark.anyio
async def test_cape_adapter_is_a_deliberately_unsupported_scope_decision():
    # No api_url needed to demonstrate this - it's not a "not configured yet" gap,
    # every call rejects outright regardless of configuration.
    adapter = CapeSandboxAdapter()

    with pytest.raises(NotImplementedError, match="not supported"):
        await adapter.analyze(b"MZ", timeout_s=0)


@pytest.mark.anyio
async def test_legacy_sandbox_wrapper_returns_context(tmp_path):
    sandbox = Sandbox(workdir=tmp_path)

    context = await sandbox.run(b"hello", timeout_s=5.0)

    assert context["bytes"] == 5
    assert context["format"] == "unknown"
    assert "sha256" in context
    sandbox.close()
