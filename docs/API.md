# Documents the stable HTTP and gRPC contracts exposed by the RAKSHAK backend.
# Backend API

Both protocols call the same `Router.decide(Event)` decision path. HTTP is intended for health
checks and simple UI actions; gRPC is intended for streaming logs and file uploads from Qt.

## Authentication

`GET /health` and `GET /v1/healthz` are public. Every scan endpoint and every gRPC method requires
the API key unless `RAKSHAK_REQUIRE_API_KEY=0`.

- HTTP header: `x-api-key: <value>`
- gRPC metadata: `x-api-key: <value>`
- Development default: `dev-key`

Always replace the development key for deployment.

## HTTP

Default address: `http://127.0.0.1:8080`

| Method | Path | Body | Result |
| --- | --- | --- | --- |
| `GET` | `/health` | none | service name, version, status |
| `GET` | `/v1/healthz` | none | service name, version, status |
| `GET` | `/metrics` | none | Prometheus text exposition, unauthenticated |
| `POST` | `/v1/scan/logline` | JSON `{ "line": "..." }` | suspicious flag and decision |
| `POST` | `/v1/scan/file` | multipart field named `file` | malicious flag, decision, SHA-256 |

Log lines must contain 1 to 65,536 characters. File uploads must be non-empty and cannot exceed
`RAKSHAK_MAX_FILE_BYTES`, which defaults to 33,554,432 bytes (32 MiB).

Log response:

```json
{
  "suspicious": true,
  "score": 0.81,
  "confidence": 0.72,
  "model": "fuse:weighted",
  "reason": "orchestrator/router"
}
```

File response:

```json
{
  "malicious": false,
  "score": 0.18,
  "confidence": 0.65,
  "model": "fuse:weighted",
  "reason": "orchestrator/router",
  "sha256": "64-character-lowercase-hex-digest"
}
```

Expected errors include `400` for an empty file, `401` for invalid credentials, `413` for a file
over the configured limit, and `422` for invalid JSON or request fields. Unexpected internal
failures return a stable `500` message without exposing exception details.

`/v1/scan/file` (default `30/minute`) and `/v1/scan/logline` (default `300/minute`) are rate
limited, keyed by `x-api-key` rather than raw IP so proxied/NAT'd clients don't throttle each
other. Override with `RAKSHAK_RATE_SCAN_FILE`/`RAKSHAK_RATE_SCAN_LOGLINE`. Exceeding the limit
returns `429`.

A confident `malicious` verdict (`confidence >= 0.5`) on `/v1/scan/file` or gRPC
`UploadAndDecide` gets the sample encrypted and moved to quarantine, removed from its original
location. The response includes `quarantined`/`quarantine_id`; see `backend/engine/quarantine.py`
for restore/list operations.

## gRPC

Default address: `127.0.0.1:50055`

The authoritative source is `backend/api/gRPC/protos/decision.proto`. The package is
`rakshak.decider.v1` and the service is `Decider`.

| RPC | Shape | Purpose |
| --- | --- | --- |
| `Decide` | unary request and response | score one log line or one small file payload |
| `StreamLogs` | bidirectional stream | correlate and score a sequence of log lines |
| `UploadAndDecide` | client stream, unary response | upload a file in bounded ordered chunks |

`Decide` rejects empty payloads. `StreamLogs` preserves each caller-provided `LogLine.id` in the
matching `LogDecision.id` and rejects empty log text.

For `UploadAndDecide`:

- Start with `offset = 0`.
- Each later offset must equal the number of bytes already sent.
- Put `path` and `context` on the first chunk.
- Mark the final chunk with `eof = true`.
- Keep individual chunks below the 16 MiB gRPC message limit; bundled clients use 128 KiB.
- The complete file cannot exceed `RAKSHAK_MAX_FILE_BYTES`.

Malformed streams return `INVALID_ARGUMENT`; oversized files return `RESOURCE_EXHAUSTED`; missing
or invalid API keys return `UNAUTHENTICATED`.

## Metrics

`GET /metrics` on the HTTP server serves Prometheus text exposition directly. gRPC has no
HTTP surface of its own, so its metrics need a separate port opened via
`RAKSHAK_METRICS_PORT` (unset by default; the gRPC process won't open that port at all
unless it's set).

| Metric | Type | Labels | Meaning |
| --- | --- | --- | --- |
| `rakshak_requests_total` | counter | `protocol`, `endpoint`, `status` | requests handled |
| `rakshak_request_latency_seconds` | histogram | `protocol`, `endpoint` | handling latency |
| `rakshak_verdicts_total` | counter | `kind`, `verdict` | decisions returned |
| `rakshak_quarantine_total` | counter | none | files moved to quarantine |

`status` is `"ok"`/HTTP status code on success and `"error"` otherwise; individual gRPC
abort reasons aren't broken out separately to keep label cardinality bounded.

## Generate Bindings

Python bindings used by the server and tests:

```powershell
.\.venv\Scripts\python.exe scripts\dev\gen_decider_proto.py
```

Python and C++ bindings for Qt integration:

```powershell
.\.venv\Scripts\python.exe scripts\dev\gen_decider_proto.py --cpp
```

Developer-generated output is placed under `build/proto/`. Distribution builds also generate and
package the Python bindings automatically. C++ generation requires `protoc` and `grpc_cpp_plugin`
on `PATH`.

## Runtime Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `RAKSHAK_API_KEY` | `dev-key` | shared HTTP and gRPC API key |
| `RAKSHAK_REQUIRE_API_KEY` | `1` | enables API-key enforcement |
| `RAKSHAK_MAX_FILE_BYTES` | `33554432` | HTTP and gRPC file limit |
| `RAKSHAK_HTTP_HOST` | `127.0.0.1` | HTTP bind address |
| `RAKSHAK_HTTP_PORT` | `8080` | HTTP port |
| `RAKSHAK_GRPC_HOST` | `127.0.0.1` | gRPC bind address |
| `RAKSHAK_GRPC_PORT` | `50055` | gRPC port |
| `RAKSHAK_LOG_LEVEL` | `info` | HTTP log level |
| `RAKSHAK_TLS` | `0` | enables gRPC TLS |
| `RAKSHAK_TLS_CERT` | `server.crt` | gRPC server certificate |
| `RAKSHAK_TLS_KEY` | `server.key` | gRPC private key |
| `RAKSHAK_SANDBOX_ADAPTER` | `bwrap` | sandbox adapter selection (`bwrap`, `static`, `dynamic`, or `cape`) |
| `RAKSHAK_RATE_SCAN_FILE` | `30/minute` | rate limit for `/v1/scan/file`, keyed by API key |
| `RAKSHAK_RATE_SCAN_LOGLINE` | `300/minute` | rate limit for `/v1/scan/logline`, keyed by API key |
| `RAKSHAK_QUARANTINE_DIR` | package-relative | where quarantined files land; set this for non-editable installs (Docker) since the default path sits inside the installed package tree |
| `RAKSHAK_MODEL_STATE_DIR` | package-relative | where the online-learning checkpoints (`hst_state.joblib`, `ngram_state.joblib`) get written; same reasoning as above |
| `RAKSHAK_METRICS_PORT` | unset | opens a Prometheus metrics HTTP server on the gRPC process at this port; unset means it doesn't open one at all |

Both servers bind to loopback by default. Binding to another interface should only be done with a
strong API key, firewall rules, and TLS appropriate to the deployment.
