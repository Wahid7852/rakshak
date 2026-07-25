# Tests the dynamic (execution-based) sandbox adapter and its strace parsing.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.engine.adapters.sandbox import DynamicSandboxAdapter, create_sandbox_adapter
from backend.engine.sandbox import dynamic_runner
from backend.engine.sandbox.dynamic_runner import _parse_trace, dynamic_context, run_dynamic


def test_parse_trace_extracts_execve_connect_and_outside_opens():
    raw = b"""\
1234 execve("/tmp/rk_dyn_x/sample", ["sample"], 0x7fff /* 20 vars */) = 0
1234 connect(3, {sa_family=AF_INET, sin_port=htons(9), sin_addr=inet_addr("127.0.0.1")}, 16) = -1 ENETUNREACH (Network unreachable)
1234 execve("/bin/true", ["true"], 0x7fff /* 0 vars */) = 0
1234 openat(AT_FDCWD, "/etc/secrets.conf", O_RDONLY) = 3
1234 openat(AT_FDCWD, "/tmp/rk_dyn_x/sample", O_RDONLY) = 4
"""
    result = _parse_trace(raw, "/tmp/rk_dyn_x")

    assert result["child_execs"] == ["/tmp/rk_dyn_x/sample", "/bin/true"]
    assert len(result["connect_attempts"]) == 1
    assert "127.0.0.1" in result["connect_attempts"][0]
    # /etc is in the always-allowed ro-bind list, so it's not "outside the sandbox"
    assert result["opens_outside_sandbox"] == []


def test_parse_trace_flags_opens_truly_outside_sandbox():
    raw = b'1234 openat(AT_FDCWD, "/home/victim/.ssh/id_rsa", O_RDONLY) = 3\n'
    result = _parse_trace(raw, "/tmp/rk_dyn_x")
    assert result["opens_outside_sandbox"] == ["/home/victim/.ssh/id_rsa"]


def test_dynamic_context_uses_dynamic_prefix_not_sandbox_prefix():
    ctx = dynamic_context({"bytes": 5, "executed": True})
    assert ctx == {"dynamic_bytes": "5", "dynamic_executed": "True"}
    assert not any(k.startswith("sandbox_") for k in ctx)


@pytest.mark.anyio
async def test_run_dynamic_refuses_non_elf_payload():
    result = await run_dynamic(b"not an ELF file at all", timeout_s=5.0)
    assert result["executed"] is False
    assert "ELF" in result["error"]


@pytest.mark.anyio
async def test_run_dynamic_executes_a_real_harmless_elf():
    # /bin/true (or /usr/bin/true) is present on every Linux CI runner and does
    # nothing but exit 0 - a real end-to-end run through bwrap+strace, no mocking.
    import shutil
    true_path = shutil.which("true")
    if true_path is None:
        pytest.skip("no `true` binary on PATH")

    payload = open(true_path, "rb").read()
    result = await run_dynamic(payload, timeout_s=5.0)

    assert result["executed"] is True
    assert result["timed_out"] is False
    assert result["bytes"] == len(payload)


@pytest.mark.anyio
async def test_run_dynamic_times_out_and_kills_process_group():
    async def hang_forever():
        await asyncio.sleep(10)

    fake_proc = MagicMock()
    fake_proc.wait = hang_forever
    fake_proc.pid = 999999

    with patch.object(dynamic_runner, "_bwrap_available", return_value=True), \
         patch.object(dynamic_runner.asyncio, "create_subprocess_exec", new=AsyncMock(return_value=fake_proc)), \
         patch.object(dynamic_runner, "_kill_group") as fake_kill:
        result = await run_dynamic(b"\x7fELF" + b"A" * 20, timeout_s=0.05)

    assert result["timed_out"] is True
    fake_kill.assert_called_once_with(fake_proc)


def test_factory_dynamic_kind_returns_dynamic_adapter():
    assert isinstance(create_sandbox_adapter("dynamic"), DynamicSandboxAdapter)


def test_factory_default_is_still_bwrap_not_dynamic(monkeypatch):
    monkeypatch.delenv("RAKSHAK_SANDBOX_ADAPTER", raising=False)
    from backend.engine.adapters.sandbox import BwrapSandboxAdapter

    assert isinstance(create_sandbox_adapter(), BwrapSandboxAdapter)
