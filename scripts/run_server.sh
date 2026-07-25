# Starts the development HTTP server with the repository virtual environment.
set -euo pipefail
export PYTHONUNBUFFERED=1
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "Missing .venv. Follow docs/getting-started.md first." >&2
  exit 1
fi
exec "$PYTHON" -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8080
