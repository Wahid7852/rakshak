# Starts the development HTTP server with the repository virtual environment.
$env:PYTHONUNBUFFERED="1"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Missing .venv. Follow docs/getting-started.md first."
}
& $python -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8080
