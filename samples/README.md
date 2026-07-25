# Sample files for testing the Qt client

Everything here is synthetic - no real malware, no real credentials. Just
fixtures for exercising Scan, Log Analysis, and Quarantine without needing
a live production log source.

## Scan a file

`quarantine-test.txt` is a deterministic fixture (same bytes every time it's
regenerated) that reliably scores `malicious: true` when scanned through the
Scan page - it has a PE header (`MZ`), high-entropy padding, and suspicious
marker strings (`cmd.exe`, `powershell -enc`, `CreateRemoteThread`, ...) that
the real detectors pick up on.

It will **not** auto-quarantine on its own - confidence caps around 0.34 with
the dynamic (execution-based) sandbox signal off by default (the default,
safety-conservative config), below the 0.5 bar `/v1/scan/file` requires
before quarantining anything. That's by design, not a bug in the sample.

## Test quarantine list/restore/delete

Since no synthetic file can cross that confidence bar under default config,
`seed_quarantine.py` writes a real entry directly via `QuarantineManager`
instead - genuinely encrypted, on-disk, listable:

```bash
.venv/bin/python samples/seed_quarantine.py
```

The running backend's `QuarantineManager` loads its on-disk db once at
startup and won't see the new entry until you restart it. Restart, open the
Quarantine page, hit Refresh - the seeded entry should be there to restore
or delete for real.

## Log analysis

`sample-auth.log` is a mix of benign and suspicious-looking auth log lines
(successful logins, repeated failed-password attempts from a few IPs, sudo
usage). Paste any line into Log Analysis's "Check line" box for an on-demand
verdict, or use it to simulate continuous background tailing:

```bash
samples/simulate_tail.sh /tmp/watched.log
```

This appends one line every 2s to whatever path you give it. Point
Settings -> Log path at that same path (and hit Save) before or while the
script runs, and RAKSHAK will tail it live - new lines show up in Raw Tail,
and any that score suspicious land in Flagged Lines and Recent Activity too.
