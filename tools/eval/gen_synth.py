# Provides tooling support for gen synth.
#!/usr/bin/env python
from __future__ import annotations
import os, pathlib, random

ROOT = pathlib.Path("data/synth").resolve()

def _ensure():
    (ROOT/"logs").mkdir(parents=True, exist_ok=True)
    (ROOT/"files"/"benign").mkdir(parents=True, exist_ok=True)
    (ROOT/"files"/"malicious").mkdir(parents=True, exist_ok=True)

def make_logs(n_ben=200, n_mal=200):
    ben = ROOT/"logs"/"benign.log"
    mal = ROOT/"logs"/"malicious.log"
    with open(ben, "w", encoding="utf-8") as fb:
        for i in range(n_ben):
            fb.write(f"Jun 17 10:{40+i%20:02d}:15 host app[{100+i}]: GET /ping 200 OK user=ubuntu\n")
    with open(mal, "w", encoding="utf-8") as fm:
        for i in range(n_mal):
            fm.write(f"Jun 17 10:{40+i%20:02d}:16 sshd[{200+i}]: Failed password for invalid user admin from 10.22.{i%5}.{i%255} port {50000+i%1000} ssh2\n")
    return str(ben), str(mal)

def make_files(n_ben=10, n_mal=10):
    # benign: text/csv-like
    for i in range(n_ben):
        with open(ROOT/"files"/"benign"/f"b{i:03d}.txt", "wb") as f:
            f.write(b"just a harmless text document\n"*20)
    # malicious-ish: PE-like header + high-entropy noise
    rng = random.Random(42)
    for i in range(n_mal):
        size = 100*1024 + (i%10)*1024
        body = bytes(rng.getrandbits(8) for _ in range(size))
        with open(ROOT/"files"/"malicious"/f"m{i:03d}.bin", "wb") as f:
            f.write(b"MZ"+body)
    return str(ROOT/"files"/"benign"), str(ROOT/"files"/"malicious")

def main():
    _ensure()
    b, m = make_logs()
    db, dm = make_files()
    print("logs:", b, m)
    print("files:", db, dm)

if __name__ == "__main__":
    main()
