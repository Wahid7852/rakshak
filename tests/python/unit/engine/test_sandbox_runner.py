# Tests run_sandboxed's timeout/failure/parsing branches and sandbox_context.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.engine.sandbox import runner


def test_sandbox_context_prefixes_keys():
    ctx = runner.sandbox_context({"bytes": 5, "format": "unknown"})
    assert ctx == {"sandbox_bytes": "5", "sandbox_format": "unknown"}


@pytest.fixture
def reset_bwrap_cache():
    original = runner._bwrap_functional
    runner._bwrap_functional = None
    yield
    runner._bwrap_functional = original


def test_bwrap_available_false_when_binary_missing(reset_bwrap_cache):
    with patch.object(runner.shutil, "which", return_value=None):
        assert runner._bwrap_available() is False


def test_bwrap_available_false_when_binary_present_but_cant_sandbox(reset_bwrap_cache):
    # this is the case a plain `docker run` hits: bwrap is on PATH but the
    # container's default seccomp profile refuses namespace creation
    with patch.object(runner.shutil, "which", return_value="/usr/bin/bwrap"), \
         patch.object(runner.subprocess, "run", return_value=MagicMock(returncode=1)):
        assert runner._bwrap_available() is False


def test_bwrap_available_true_when_probe_succeeds(reset_bwrap_cache):
    with patch.object(runner.shutil, "which", return_value="/usr/bin/bwrap"), \
         patch.object(runner.subprocess, "run", return_value=MagicMock(returncode=0)) as fake_run:
        assert runner._bwrap_available() is True
    fake_run.assert_called_once()


def test_bwrap_available_result_is_cached(reset_bwrap_cache):
    with patch.object(runner.shutil, "which", return_value="/usr/bin/bwrap"), \
         patch.object(runner.subprocess, "run", return_value=MagicMock(returncode=0)) as fake_run:
        runner._bwrap_available()
        runner._bwrap_available()
        runner._bwrap_available()
    fake_run.assert_called_once()  # probed once, reused after


@pytest.mark.anyio
async def test_run_sandboxed_real_worker_detects_pe_and_suspicious_strings():
    # exercises the real bwrap-or-fallback subprocess path end to end
    payload = b"MZ" + b"A" * 50 + b"powershell -enc AAAA"
    result = await runner.run_sandboxed(payload, timeout_s=5.0)

    assert result["format"] == "pe"
    assert "powershell" in result["suspicious_strings"]
    assert result["bytes"] == len(payload)
    assert result["timed_out"] is False


@pytest.mark.anyio
async def test_run_sandboxed_times_out_gracefully():
    async def hang_forever():
        await asyncio.sleep(10)
        return b"", b""

    fake_proc = MagicMock()
    fake_proc.communicate = hang_forever
    fake_proc.pid = 999999

    with patch.object(runner.asyncio, "create_subprocess_exec", new=AsyncMock(return_value=fake_proc)), \
         patch.object(runner, "_kill_group") as fake_kill:
        result = await runner.run_sandboxed(b"payload", timeout_s=0.05)

    assert result["timed_out"] is True
    assert result["error"] == "analysis timed out"
    fake_kill.assert_called_once_with(fake_proc)


@pytest.mark.anyio
async def test_run_sandboxed_handles_worker_failure():
    fake_proc = MagicMock()
    fake_proc.communicate = AsyncMock(return_value=(b"", b"boom"))
    fake_proc.returncode = 1

    with patch.object(runner.asyncio, "create_subprocess_exec", new=AsyncMock(return_value=fake_proc)):
        result = await runner.run_sandboxed(b"payload", timeout_s=5.0)

    assert result["error"] == "analysis worker failed"
    assert result["timed_out"] is False


@pytest.mark.anyio
async def test_run_sandboxed_handles_unparseable_output():
    fake_proc = MagicMock()
    fake_proc.communicate = AsyncMock(return_value=(b"not json at all", b""))
    fake_proc.returncode = 0

    with patch.object(runner.asyncio, "create_subprocess_exec", new=AsyncMock(return_value=fake_proc)):
        result = await runner.run_sandboxed(b"payload", timeout_s=5.0)

    assert result["error"] == "unparseable worker output"
    assert result["timed_out"] is False
