# Introduces RAKSHAK and the shortest reliable path to a running backend.
# RAKSHAK

RAKSHAK is a local-first decision backend (HTTP + gRPC) built around one cascading
orchestrator (`backend/orchestrator/`) that runs cheap detectors first and only escalates to
expensive ones for borderline cases. Two capabilities sit on top of that same core:

- **Malware/log detection** - file and log-line scanning cascade (below).
- **Insider-threat hunting** - a central node ingesting per-employee login/file-access/
  data-transfer events from thin collector agents, baselining each employee against their
  own history and scoring deviations with severity and a plain-language reason. See
  "Insider-threat hunting" further down, and `hackathon/` for the full writeup.

The active runtime lives under `backend/`; training and research code stay separate from
request serving.

Detectors, all real, all trained on real data (see `docs/results.md` for
measured numbers):

- `log_hst` / `log_ngram` - unsupervised streaming anomaly detection over log lines, calibrate online, no training needed.
- `log_sgd` - online logistic regression, pretrained on LogHub HDFS_v1.
- `file_static` - entropy/header heuristic over raw file bytes.
- `file_ml_or_rf` - LightGBM classifier on EMBER2018 PE features (AUC 0.99).
- `file_sandbox_signal` - fed by a read-only, bwrap-isolated static analysis pass (never executes the sample).
- `file_qsvc` - quantum-embedded SVM, borderline-case tie-breaker only (AUC 0.69, honestly modest).

## Requirements

- Python >= 3.11
- [bubblewrap](https://github.com/containers/bubblewrap) (`bwrap`) on `PATH` for the sandbox analysis step to run isolated - falls back to a degraded rlimit-only mode if missing, with a logged warning.

## Setup

```bash
pip install -e .
# or, on distros that block system-wide pip installs (Arch/CachyOS etc):
pip install --user --break-system-packages -e .
```

Optional extras:

```bash
pip install -e ".[quantum]"   # pennylane, qiskit - needed for file_qsvc to run for real, otherwise it neutral-falls-back
pip install -e ".[train]"     # datasets, huggingface-hub - only needed to re-run scripts/dev/train_*.py
pip install -e ".[dev]"       # pytest, ruff, mypy, bandit, pip-audit, schemathesis, hypothesis, ...
```

## Running

REST API:

```bash
rakshak-http
# or directly: python -m uvicorn backend.api.main:app --port 8000
```

gRPC:

```bash
python scripts/dev/gen_decider_proto.py   # generates build/proto/py, needed once (gitignored, not committed)
rakshak-grpc
# or directly: python -m backend.api.gRPC.decider_server --port 50055
```

Defaults: HTTP `127.0.0.1:8080`, gRPC `127.0.0.1:50055`, API key `dev-key`. Set
`RAKSHAK_API_KEY` before any non-development deployment.

Auth: every route except `/health` and `/v1/healthz` needs an `x-api-key`
header. Defaults to `dev-key` for local dev - set `RAKSHAK_API_KEY` to
override for anything beyond that. TLS on the gRPC server is off by
default; set `RAKSHAK_TLS=1` and drop `server.crt`/`server.key` in the
working directory to enable it.

Rate limits: `/v1/scan/file` (30/minute) and `/v1/scan/logline` (300/minute)
by default, keyed by `x-api-key` (not raw IP, so proxied/NAT'd clients don't
throttle each other). Override with `RAKSHAK_RATE_SCAN_FILE`/
`RAKSHAK_RATE_SCAN_LOGLINE` (e.g. `"10/minute"`). Exceeding the limit
returns `429`.

Quarantine: a confident `malicious` verdict (`confidence >= 0.5`) on
`/scan/file` or gRPC `UploadAndDecide` gets the sample encrypted and moved
to `<repo root>/quarantine/` (gitignored, not repo content), removed from
its original location. The response includes `quarantined`/`quarantine_id`.
See `backend/engine/quarantine.py` for restore/list operations.

## Docker

```bash
docker build -t rakshak-backend .
docker run -d -p 8080:8080 -e RAKSHAK_API_KEY=your-key rakshak-backend        # HTTP
docker run -d -p 50055:50055 -e RAKSHAK_API_KEY=your-key rakshak-backend rakshak-grpc  # gRPC

# or both at once, sharing a quarantine volume:
docker compose up
```

Runs as a non-root user with quarantine and the online-learning checkpoints redirected
to a dedicated writable directory (see `RAKSHAK_QUARANTINE_DIR`/`RAKSHAK_MODEL_STATE_DIR`
in `docs/API.md`), since a regular `pip install` copies the package into site-packages
rather than leaving it in a writable source tree.

`bubblewrap` is installed in the image, but a plain `docker run` doesn't grant the
namespace privileges it needs; static analysis automatically degrades to the
rlimit-only fallback in that case rather than failing every scan. Run with `--privileged`
if you want real bwrap isolation inside the container, understanding that this gives the
container broad host access in exchange, which is not a trade worth making by default.

## API quickstart

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/v1/scan/logline \
  -H "x-api-key: dev-key" -H "Content-Type: application/json" \
  -d '{"line": "auth failure user=root from=185.220.101.5"}'

curl -X POST http://localhost:8000/v1/scan/file \
  -H "x-api-key: dev-key" -F "file=@/path/to/sample.exe"
```

## Insider-threat hunting

One central RAKSHAK node, thin collector agents on each monitored machine forwarding
login/file-access/data-transfer events - not one RAKSHAK per employee. Per-employee
behavioral baselines, unsupervised anomaly scoring, severity with a plain-language reason.
Full design in `hackathon/technical-approach.md`.

```bash
# generate simulated per-employee logs (a minority carry an injected insider pattern)
python samples/insider/generate_employee_logs.py --employees 12 --insiders 3

# central node
rakshak-http

# collector agent - tails the generated logs, forwards batches to the ingest endpoint
python scripts/agent/collector.py --source samples/insider/logs --server http://127.0.0.1:8080 --once

# severity-scored alert feed
curl -H "x-api-key: dev-key" "http://127.0.0.1:8080/v1/insider/alerts?min_severity=high"

# dashboard
open http://127.0.0.1:8080/insider/dashboard
```

Real output from a run of the above (12 employees, 3 injected insider scenarios, seed 21):

```
$ python samples/insider/generate_employee_logs.py --employees 12 --insiders 3 --seed 21
wrote 2496 events across 12 employees to samples/insider/logs
injected insider scenarios: {'EMP004': 'resignation_exfil', 'EMP002': 'staged_exfil', 'EMP003': 'odd_hours_new_host'}
hr signals: {'EMP004': 'resignation_submitted', 'EMP011': 'offboarding_scheduled (control - no anomalous behavior)'}

$ curl -H "x-api-key: dev-key" http://127.0.0.1:8080/v1/insider/users/EMP004
{
  "employee_id": "EMP004", "risk": 1.0, "severity": "critical",
  "narrative": "EMP004 is at critical risk (score 1.00), driven by file access activity.
    Recent signals: activity outside normal working hours; elevated scrutiny: employee is
    in a departing/offboarding or PIP window. ~46.4MB of activity in the trailing 14 days.",
  "blast_radius_bytes": 48692661.5
}
```

All 3 injected insiders (`EMP002`, `EMP003`, `EMP004`) were flagged critical; all 9 normal
employees, including `EMP011` (an HR lifecycle signal with zero anomalous behavior, there
specifically to prove the signal alone doesn't manufacture an alert), stayed low.

## Tests

```bash
python scripts/dev/gen_decider_proto.py   # gRPC tests need the generated stubs, see above
python -m pytest -q
```

See `docs/results.md`'s "Fixed along the way" section for what installing
`pennylane` here uncovered (and fixed) in the quantum feature map.

## Retraining detectors

```bash
python scripts/dev/train_log_sgd.py     # needs data/raw/hdfs/HDFS_v1.zip - see LogHub, Zenodo record 8196385
python scripts/dev/train_file_rf.py     # streams EMBER2018 via huggingface_hub, needs the [train] extra
python scripts/dev/train_qsvc.py        # same EMBER source, needs the [quantum] extra too
```

Each writes its artifact + a `*_meta.json` with real measured metrics to
`backend/engine/models/artifacts/`.

## Layout

```
backend/
  api/            FastAPI routers + gRPC server/client
  orchestrator/   the cascade: decision.py (router), registry.py (detectors), policies.py
  engine/
    models/       detector implementations (classical/, quantum/) + trained artifacts/
    features/     feature extraction shared by detectors
    insider/      per-employee baseline, anomaly, risk, and alert engine
    sandbox/      read-only bwrap-isolated file analysis worker
    quarantine.py encrypted quarantine storage
scripts/dev/      codegen + training scripts
scripts/agent/    collector agent (runs on a monitored machine, not the central node)
samples/insider/  simulated employee log generator for the insider-threat demo
backend/api/gRPC/protos/  gRPC service definitions
client-qt/        Qt desktop client (talks to the FastAPI backend over REST)
site/             static landing/demo/docs site, deployable to Vercel/Render (see site/README.md)
```

See [Getting Started](docs/getting-started.md), [API](docs/API.md), and
[Architecture](docs/ARCHITECTURE.md) for the full workflow, including the Windows/PowerShell
setup path.
