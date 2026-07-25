# Security Hardening (Quick List)

- Use API key/HMAC between UI and backend; store secrets outside VCS.
- Run backend as non-admin; sandbox/quarantine with least privilege.
- [x] CAPE Sandbox integration deliberately not built. `CapeSandboxAdapter` in
  `backend/engine/adapters/sandbox.py` exists only so `RAKSHAK_SANDBOX_ADAPTER=cape`
  fails with a clear explanation, not a crash somewhere unrelated. Considered and
  rejected: CAPE needs its own VM-based detonation host, real infra to run and
  maintain, and the only gap it would close here is Windows PE dynamic execution
  (`DynamicSandboxAdapter` already covers ELF). PE stays static-only; `pe_features.py`
  already extracts imports/sections/entropy/packer heuristics, which carries the real
  signal for a tool this size. Revisit only if static PE analysis turns out to miss
  something in practice, not speculatively.
- [x] Real dynamic/behavioral sandbox. `DynamicSandboxAdapter`
  (`backend/engine/sandbox/dynamic_runner.py`) actually executes ELF samples inside the
  same bwrap jail as the static worker: network, PID, and mount namespaces are all
  isolated, CPU and memory are rlimited, and a wall-clock timeout kills the whole process
  group. `strace` captures behavior (child process spawns, connect attempts, file opens
  outside the sandbox). Non-ELF payloads such as Windows PE or scripts get a clean "not
  executed" result rather than a crash. **Off by default**; `RAKSHAK_SANDBOX_ADAPTER`
  stays `bwrap` for static analysis unless someone sets it to `dynamic` explicitly. This
  is a different risk class than static analysis because it runs attacker-supplied
  bytes, jailed or not, and namespace isolation plus rlimits plus no network is not a
  security boundary against a kernel exploit or a sandbox escape. If this ever gets
  turned on it needs to run on a disposable worker host that's rebuilt after use, never
  inline with the API process, and that worker should be treated as compromised by
  default. Verified by hand with two harmless self-compiled test binaries (a plain
  exec-and-connect test, and a busy loop to confirm the timeout kills it) before any of
  this got written up; the test file does the same drill without needing a C compiler in
  CI, since `/bin/true` already covers the real-execution smoke test. Now wired to a
  detector too: `orchestrator/registry.py`'s `file_dynamic_signal` reads the
  `dynamic_*` context keys the same way `file_sandbox_signal` reads `sandbox_*`, so
  flipping the env var on actually changes verdicts, not just logs.
- [x] Verify model artifact integrity with SHA-256 manifest. `backend/engine/models/
  artifact_integrity.py` checks `file_rf.joblib`, `qsvc.joblib`, and `log_sgd.json`
  against `backend/engine/models/artifacts/manifest.json` before load; a mismatch or
  missing manifest entry raises and the model falls back to `None` (neutral verdict),
  same graceful-degradation path as any other load failure. Training scripts update the
  manifest automatically after writing a fresh artifact. Deliberately excludes
  `hst_state.joblib`/`ngram_state.joblib`, since those are online-learning checkpoints
  the running service rewrites itself, and a static hash would just go stale. Legacy
  `service/` (the pre-backend training/research code) still loads unchecked; that's out
  of scope since it isn't on the request-serving path.
- [x] Docker packaging. `Dockerfile` builds the pip-installable package with
  bubblewrap and strace baked in, running as a non-root user. Two real things came out of
  actually running the built image rather than just writing it. First, `pip install .`
  (non-editable) copies the package into site-packages, so quarantine and the
  online-learning checkpoints (`hst_state.joblib`/`ngram_state.joblib`) can't live at
  their dev-mode default paths inside the installed tree owned by root; they're now
  redirected to `RAKSHAK_QUARANTINE_DIR`/`RAKSHAK_MODEL_STATE_DIR`, both pointed at a
  dedicated writable `/app/var/` directory in the image. Second, and more important:
  bwrap is present in a plain `docker run` but can't actually create namespaces there,
  since Docker's default seccomp profile blocks the syscalls it needs, and this held even
  with `--cap-add ALL` plus an unconfined seccomp profile; only `--privileged` got it
  working, which gives up too much container isolation to use by default. Rather than
  ship that trade-off, `_bwrap_available()` in `sandbox/runner.py` now actually tries to
  create a sandbox instead of just checking whether the binary exists, so the container
  correctly falls back to the documented rlimit-only mode instead of silently failing
  every single scan. `docker-compose.yml` runs the HTTP and gRPC services from the same
  image with a shared quarantine volume.
- Pin & hash dependencies (pip-compile --generate-hashes).
- Enable HTTPS/TLS for remote deployments.
- [x] Log minimally; avoid PII. Use JSON lines. `backend/observability/request_id.py`
  gives both entry points one JSON-line-per-record formatter and binds a short id to
  every HTTP request and gRPC call (via `track_request` in `metrics.py`), so grepping
  one `request_id` across a service's log pulls every line from that call. This is
  single-hop correlation, not distributed tracing: there's no inbound trace-header
  propagation, just a fresh id generated per call. Log rotation is still left to the
  deployment (systemd/journald, Docker's log driver, or an external collector), not
  handled in-process.
- [x] Add Bandit & Ruff in CI; block on high severity. Bandit blocks on medium/high
  (`-r backend -ll`, currently 0 findings). Ruff blocks on `backend/`; repo-wide is
  report-only (`--exit-zero`) until the legacy dirs are cleaned up. mypy is now a real
  gate too. All 29 original errors are fixed: lazy-init Optional patterns got explicit
  types and asserts, `Event.context`/`_sandbox_context` switched from invariant `dict` to
  `Mapping`/matching return types, two vendored/third-party mismatches got targeted
  `type: ignore` comments). pip-audit (against the installed env), gitleaks, and a
  coverage floor (`--cov-fail-under=76`, currently 79%) round out the CI gates.
