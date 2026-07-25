# Runs a bounded, bwrap-isolated EXECUTION of a sample and captures its
# behavior via strace. Unlike runner.py (read-only, never executes), this
# module actually runs untrusted attacker-supplied bytes.
#
# SAFETY: this is a materially different risk class than static analysis.
# Isolation here is namespaces + rlimits + no network + a hard timeout, the
# same primitives Flatpak/bwrap sandboxing relies on generally - it is NOT
# a security boundary against a kernel exploit or a sufficiently clever
# sandbox escape. Do not run this inline on the same host as the API
# process in production; run it on a disposable worker that gets rebuilt
# after each use, and treat that worker as assume-compromised. Off by
# default (RAKSHAK_SANDBOX_ADAPTER=dynamic to opt in) - see docs/SECURITY.md.
from __future__ import annotations

import asyncio, logging, os, re, resource, shutil, signal, sys, tempfile
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_MEM_LIMIT_BYTES = 256 * 1024 * 1024
_CPU_LIMIT_SECONDS = 5
_ELF_MAGIC = b"\x7fELF"

_EXECVE_RE = re.compile(rb'^\d+\s+execve\("([^"]+)"')
_CONNECT_RE = re.compile(rb"connect\(\d+,\s*(\{[^}]*\})")
_OPEN_RE = re.compile(rb'openat?\([^,]*,\s*"([^"]+)"')


def _bwrap_available() -> bool:
    return shutil.which("bwrap") is not None and shutil.which("strace") is not None


def _limit_resources() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (_CPU_LIMIT_SECONDS, _CPU_LIMIT_SECONDS))
    resource.setrlimit(resource.RLIMIT_AS, (_MEM_LIMIT_BYTES, _MEM_LIMIT_BYTES))


def _bwrap_argv(scratch_dir: Path, sample_path: Path, trace_path: Path) -> list:
    ro_binds: list = []
    seen: set = set()
    for p in ("/usr", "/lib", "/lib64", "/etc", sys.prefix, sys.exec_prefix):
        if p and p not in seen and Path(p).is_dir():
            seen.add(p)
            ro_binds += ["--ro-bind", p, p]

    return [
        "bwrap",
        "--unshare-all",         # no network, no host PID/mount/IPC visibility
        "--die-with-parent",
        "--new-session",
        "--clearenv",
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",  # nosec B108 - fresh empty tmpfs in the sandboxed child's own mount namespace
        *ro_binds,
        "--bind", str(scratch_dir), str(scratch_dir),
        "--chdir", str(scratch_dir),
        "strace", "-f", "-qq",
        "-e", "trace=execve,connect,openat,open,write,unlink,unlinkat",
        "-o", str(trace_path),
        str(sample_path),
    ]


def _kill_group(proc: "asyncio.subprocess.Process") -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _parse_trace(raw: bytes, scratch_dir: str) -> Dict[str, Any]:
    execs, connects, opens_outside = [], [], set()
    for line in raw.splitlines():
        m = _EXECVE_RE.search(line)
        if m:
            execs.append(m.group(1).decode(errors="replace"))
            continue
        m = _CONNECT_RE.search(line)
        if m:
            connects.append(m.group(1).decode(errors="replace"))
            continue
        m = _OPEN_RE.search(line)
        if m:
            path = m.group(1).decode(errors="replace")
            if not path.startswith(scratch_dir) and not path.startswith(("/lib", "/usr", "/etc", "/proc", "/dev")):
                opens_outside.add(path)

    return {
        "child_execs": execs,
        "connect_attempts": connects,
        "opens_outside_sandbox": sorted(opens_outside),
    }


async def run_dynamic(payload: bytes, timeout_s: float = 5.0) -> Dict[str, Any]:
    """Execute payload as an ELF binary inside a bwrap jail with no network,
    capturing behavior via strace. Refuses anything that isn't ELF - no Wine,
    no PE execution support. Best-effort: returns a dict, never raises."""
    if not payload.startswith(_ELF_MAGIC):
        return {"bytes": len(payload), "executed": False, "error": "not an ELF binary, dynamic analysis skipped"}

    if not _bwrap_available():
        return {"bytes": len(payload), "executed": False, "error": "bwrap or strace not available"}

    scratch = Path(tempfile.mkdtemp(prefix="rk_dyn_"))
    sample_path = scratch / "sample"
    trace_path = scratch / "trace.log"
    sample_path.write_bytes(payload)
    sample_path.chmod(0o700)

    argv = _bwrap_argv(scratch, sample_path, trace_path)
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            preexec_fn=_limit_resources,
            start_new_session=True,
        )
    except FileNotFoundError:
        shutil.rmtree(scratch, ignore_errors=True)
        return {"bytes": len(payload), "executed": False, "error": "sandbox launch failed"}

    timed_out = False
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout_s)
    except asyncio.TimeoutError:
        timed_out = True
        _kill_group(proc)

    raw = trace_path.read_bytes() if trace_path.exists() else b""
    signals = _parse_trace(raw, str(scratch))
    shutil.rmtree(scratch, ignore_errors=True)

    signals.update({"bytes": len(payload), "executed": True, "timed_out": timed_out})
    return signals


def dynamic_context(signals: Dict[str, Any]) -> Dict[str, str]:
    """Flatten dynamic-analysis signals into the string-valued context dict
    detectors read, same convention as runner.py::sandbox_context."""
    return {f"dynamic_{k}": str(v) for k, v in signals.items()}
