#!/usr/bin/env python3
# Seeds one real quarantine entry for testing the Quarantine page's list/restore/delete flow.
#
# Scanning even a deliberately malicious-looking file through the Scan page won't
# auto-quarantine under default settings - confidence caps around 0.34 with the
# dynamic (execution-based) sandbox signal off by default, below the 0.5 bar
# /v1/scan/file requires. That's a deliberate safety design, not a bug. This
# script writes a real entry directly via QuarantineManager instead, so you can
# test restore/delete against genuine (encrypted, on-disk) state.
#
# Usage:
#     .venv/bin/python samples/seed_quarantine.py [file_to_quarantine]
# Defaults to samples/quarantine-test.txt if no path is given.
#
# Note: the running backend's QuarantineManager loads its on-disk db once at
# startup and doesn't re-read it per request - restart the backend (or the
# gRPC/HTTP process serving it) after running this so /v1/quarantine picks up
# the new entry.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api.config import settings
from backend.engine.quarantine import QuarantineManager


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "quarantine-test.txt"
    if not src.is_file():
        print(f"no such file: {src}", file=sys.stderr)
        return 1

    # quarantine_file() reads, encrypts, then deletes the ORIGINAL - seed
    # from a throwaway copy so samples/quarantine-test.txt stays intact for
    # reuse (e.g. scanning it again through the Scan page).
    tmp = src.parent / f"_seed_{src.name}"
    tmp.write_bytes(src.read_bytes())

    mgr = QuarantineManager(settings.quarantine_dir)
    entry = mgr.quarantine_file(tmp, reason="seeded by samples/seed_quarantine.py for UI testing")
    if entry is None:
        print("quarantine_file() failed", file=sys.stderr)
        return 1

    print(f"quarantined: id={entry.quarantine_id} sha256={entry.sha256}")
    print(f"quarantine dir: {mgr.dir}")
    print("Restart the backend for /v1/quarantine (and the Quarantine page) to see it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
