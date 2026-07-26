# Explains how to install, run, and verify the RAKSHAK backend locally.
# Getting Started

## Requirements

- Python 3.11 or newer
- Git
- `protoc` and `grpc_cpp_plugin` only when generating C++ bindings

The normal backend and test workflow does not require quantum packages, CAPE, malware samples,
or the Qt toolchain.

## Install

From the repository root on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts\dev\gen_decider_proto.py
```

On Linux or macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python scripts/dev/gen_decider_proto.py
```

The editable install provides `rakshak-http` and `rakshak-grpc` commands inside the venv.

## Configure

Development defaults work without an `.env` file. Production deployments should set at least:

```powershell
$env:RAKSHAK_API_KEY = "replace-with-a-long-random-secret"
$env:RAKSHAK_REQUIRE_API_KEY = "1"
```

Optional runtime variables are documented in [API.md](API.md).

## Run HTTP

```powershell
.\.venv\Scripts\rakshak-http.exe
```

Check the public health route:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
```

Scan a log line:

```powershell
$headers = @{ "x-api-key" = "dev-key" }
$body = @{ line = "authentication failure from 10.0.0.1" } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8080/v1/scan/logline `
  -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

## Run gRPC

In another terminal:

```powershell
.\.venv\Scripts\rakshak-grpc.exe
```

Exercise the unary client:

```powershell
.\.venv\Scripts\python.exe -m backend.api.gRPC.clients.cli_decide `
  --kind log --text "authentication failure from 10.0.0.1"
```

Generate C++ bindings later, when the Qt toolchain is installed:

```powershell
.\.venv\Scripts\python.exe scripts\dev\gen_decider_proto.py --cpp
```

## Test

```powershell
.\.venv\Scripts\python.exe scripts\check_style.py
.\.venv\Scripts\python.exe -m pytest -q
```

## Common Problems

- `Generated decider gRPC stubs are missing`: run `scripts/dev/gen_decider_proto.py`.
- `UNAUTHENTICATED`: pass the same `RAKSHAK_API_KEY` to the client and server.
- Port already in use: set `RAKSHAK_HTTP_PORT` or `RAKSHAK_GRPC_PORT`.
- C++ generation fails: install both `protoc` and `grpc_cpp_plugin`, then ensure they are on `PATH`.
