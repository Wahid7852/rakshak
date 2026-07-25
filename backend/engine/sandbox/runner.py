# Runs the read-only analysis worker under bwrap isolation.
from __future__ import annotations

import asyncio, json, logging, os, resource, shutil, signal, subprocess, sys, tempfile
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_WORKER = Path(__file__).with_name("worker.py")

_MEM_LIMIT_BYTES = 256 * 1024 * 1024
_CPU_LIMIT_SECONDS = 5

_bwrap_functional: bool | None = None  # cached after the first real probe


def _ro_binds() -> list:
    ro_binds: list = []
    seen: set = set()
    for p in ("/usr", "/lib", "/lib64", "/etc", sys.prefix, sys.exec_prefix):
        if p and p not in seen and Path(p).is_dir():
            seen.add(p)
            ro_binds += ["--ro-bind", p, p]
    return ro_binds


def _bwrap_available() -> bool:
    """Whether bwrap can actually create an isolated sandbox here, not just
    whether the binary exists. The two diverge inside a plain `docker run`:
    bwrap is present but namespace creation is refused by the container's
    default seccomp profile, so a presence-only check would keep trying (and
    failing) the bwrap path on every single scan instead of ever falling back
    to the documented rlimit-only mode. Probed once and cached, since it's the
    same answer for the life of the process. Runs the real interpreter under
    the same ro-binds the actual worker invocation uses, since a bare exec
    with nothing bound just fails at the dynamic linker and proves nothing."""
    global _bwrap_functional
    if _bwrap_functional is not None:
        return _bwrap_functional

    if shutil.which("bwrap") is None:
        _bwrap_functional = False
        return False

    try:
        probe = subprocess.run(
            [
                "bwrap", "--unshare-all", "--die-with-parent", "--proc", "/proc",
                *_ro_binds(), "--", sys.executable, "-c", "pass",
            ],
            capture_output=True,
            timeout=5,
        )
        _bwrap_functional = probe.returncode == 0
    except Exception:
        _bwrap_functional = False

    if not _bwrap_functional:
        logger.warning("bwrap is present but couldn't create a sandbox in this environment; falling back to rlimit-only")
    return _bwrap_functional


def _limit_resources() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (_CPU_LIMIT_SECONDS, _CPU_LIMIT_SECONDS))
    resource.setrlimit(resource.RLIMIT_AS, (_MEM_LIMIT_BYTES, _MEM_LIMIT_BYTES))


def _bwrap_argv(scratch_dir: Path, sample_path: Path) -> list:
    return [
        "bwrap",
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--clearenv",
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",  # nosec B108 - bwrap arg: fresh empty tmpfs inside the sandboxed child's own mount namespace, not a shared host path
        *_ro_binds(),
        "--ro-bind", str(_WORKER), str(_WORKER),
        "--bind", str(scratch_dir), str(scratch_dir),
        "--chdir", str(scratch_dir),
        sys.executable, str(_WORKER), str(sample_path),
    ]


def _kill_group(proc: "asyncio.subprocess.Process") -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


async def run_sandboxed(payload: bytes, timeout_s: float = 5.0) -> Dict[str, Any]:
    """Read-only static analysis of untrusted bytes. Never executes the sample.

    Isolated with bwrap when available (no network, no filesystem access
    beyond the worker script and a private scratch dir); falls back to a
    plain rlimit-constrained subprocess if bwrap isn't installed.
    """
    scratch = Path(tempfile.mkdtemp(prefix="rk_sbx_"))
    sample_path = scratch / "sample.bin"
    sample_path.write_bytes(payload)

    use_bwrap = _bwrap_available()
    if use_bwrap:
        argv = _bwrap_argv(scratch, sample_path)
        preexec = None
    else:
        logger.warning("bwrap unavailable; running sandbox worker unsandboxed with rlimits only")
        argv = [sys.executable, str(_WORKER), str(sample_path)]
        preexec = _limit_resources

    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=preexec,
            start_new_session=True,
        )
    except FileNotFoundError:
        shutil.rmtree(scratch, ignore_errors=True)
        logger.error("sandbox worker launch failed: %s not found", argv[0])
        return {"bytes": len(payload), "error": "sandbox unavailable", "timed_out": False}

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        _kill_group(proc)
        shutil.rmtree(scratch, ignore_errors=True)
        return {"bytes": len(payload), "timed_out": True, "error": "analysis timed out"}

    shutil.rmtree(scratch, ignore_errors=True)

    if proc.returncode != 0 or not stdout:
        logger.warning("sandbox worker failed rc=%s stderr=%s", proc.returncode, stderr[:500])
        return {"bytes": len(payload), "error": "analysis worker failed", "timed_out": False}

    try:
        result: Dict[str, Any] = json.loads(stdout.decode().strip().splitlines()[-1])
    except (ValueError, IndexError):
        logger.warning("sandbox worker produced unparseable output: %r", stdout[:500])
        return {"bytes": len(payload), "error": "unparseable worker output", "timed_out": False}

    result.setdefault("bytes", len(payload))
    result["timed_out"] = False
    return result


def sandbox_context(signals: Dict[str, Any]) -> Dict[str, str]:
    """Flatten sandbox signals into the string-valued context dict detectors read."""
    return {f"sandbox_{k}": str(v) for k, v in signals.items()}
