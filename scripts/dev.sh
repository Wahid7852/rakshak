# Starts the RAKSHAK backend and the Qt desktop client together for local dev.
# First run creates .venv and configures the client-qt build; later runs are fast.
# Ctrl+C or closing the GUI window stops the backend too.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VENV_PYTHON="$ROOT/.venv/bin/python"
BUILD_DIR="$ROOT/client-qt/build"
HOST="127.0.0.1"
PORT="8080"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "==> No .venv found, creating one with python3.11..."
  python3.11 -m venv "$ROOT/.venv"
  "$VENV_PYTHON" -m pip install --upgrade pip -q
fi

echo "==> Ensuring backend deps are installed (fast no-op if already up to date)..."
"$VENV_PYTHON" -m pip install -e "$ROOT[dev]" -q

echo "==> Starting backend on http://$HOST:$PORT ..."
RAKSHAK_API_KEY="${RAKSHAK_API_KEY:-dev-key}" "$VENV_PYTHON" -m uvicorn backend.api.main:app --host "$HOST" --port "$PORT" &
BACKEND_PID=$!
trap 'echo "==> Stopping backend (pid $BACKEND_PID)..."; kill "$BACKEND_PID" 2>/dev/null || true' EXIT

echo -n "==> Waiting for backend to answer /health"
for _ in $(seq 1 30); do
  if curl -s -o /dev/null "http://$HOST:$PORT/health"; then
    echo " - up."
    break
  fi
  echo -n "."
  sleep 0.5
done

echo "==> Configuring/building the Qt client (client-qt/build)..."
cmake -S "$ROOT/client-qt" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Debug
cmake --build "$BUILD_DIR" -j"$(nproc)"

echo "==> Launching rakshak_gui..."
"$BUILD_DIR/rakshak_gui"
