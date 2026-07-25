#!/usr/bin/env python3
# Read-only static analysis worker, runs inside a bwrap jail. Never executes
# the sample. Stdlib-only so the sandbox doesn't need the repo bind-mounted.
import hashlib, json, math, re, sys
from collections import Counter

SUSPICIOUS = (
    b"cmd.exe", b"powershell", b"/bin/sh", b"http://", b"https://",
    b"CreateRemoteThread", b"VirtualAlloc", b"WinExec", b"base64,",
)

MAGIC = (
    (b"MZ", "pe"),
    (b"\x7fELF", "elf"),
    (b"PK\x03\x04", "zip"),
    (b"%PDF", "pdf"),
    (b"\x89PNG", "png"),
)

HEAD_BYTES = 200 * 1024
STRINGS_LIMIT = 16
STRINGS_MIN_LEN = 4


def entropy(b: bytes) -> float:
    if not b:
        return 0.0
    n = len(b)
    counts = Counter(b)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def sniff_format(b: bytes) -> str:
    for magic, name in MAGIC:
        if b.startswith(magic):
            return name
    return "unknown"


def printable_strings(b: bytes, min_len: int = STRINGS_MIN_LEN, limit: int = STRINGS_LIMIT):
    out = []
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % min_len, b):
        out.append(m.group().decode("ascii"))
        if len(out) >= limit:
            break
    return out


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: worker.py <sample_path>"}))
        return 2

    with open(sys.argv[1], "rb") as f:
        data = f.read()

    head = data[:HEAD_BYTES]
    hits = sorted({s.decode() for s in SUSPICIOUS if s in data})

    result = {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "entropy": round(entropy(head), 4),
        "format": sniff_format(data),
        "suspicious_strings": hits,
        "strings_sample": printable_strings(head),
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
