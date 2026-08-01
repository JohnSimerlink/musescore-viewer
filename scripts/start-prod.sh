#!/usr/bin/env bash
# Production entrypoint: Python agent sidecar + Node UI in one container.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PORT="${PORT:-8080}"
export COPLAND_AGENT_HOST="${COPLAND_AGENT_HOST:-127.0.0.1}"
export COPLAND_AGENT_PORT="${COPLAND_AGENT_PORT:-5178}"
export COPLAND_AGENT_URL="${COPLAND_AGENT_URL:-http://${COPLAND_AGENT_HOST}:${COPLAND_AGENT_PORT}}"
export COPLAND_SEED_DIR="${COPLAND_SEED_DIR:-${ROOT}/public/seed}"

VENV_PY="${ROOT}/agent/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "Missing agent venv at ${VENV_PY}" >&2
  exit 1
fi

port_in_use() {
  "$VENV_PY" - <<PY
import socket
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("${COPLAND_AGENT_HOST}", int("${COPLAND_AGENT_PORT}")))
except OSError:
    raise SystemExit(0)
else:
    s.close()
    raise SystemExit(1)
PY
}

if port_in_use; then
  echo "Agent port ${COPLAND_AGENT_HOST}:${COPLAND_AGENT_PORT} already in use" >&2
  exit 1
fi

cleanup() {
  if [[ -n "${AGENT_PID:-}" ]] && kill -0 "$AGENT_PID" 2>/dev/null; then
    kill "$AGENT_PID" 2>/dev/null || true
    wait "$AGENT_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting Copland agent on ${COPLAND_AGENT_HOST}:${COPLAND_AGENT_PORT}"
(
  cd "${ROOT}/agent"
  COPLAND_AGENT_RELOAD=0 exec "$VENV_PY" -m copland_agent
) &
AGENT_PID=$!

ready=0
for _ in $(seq 1 50); do
  if ! kill -0 "$AGENT_PID" 2>/dev/null; then
    echo "Agent process exited before becoming healthy" >&2
    wait "$AGENT_PID" || true
    exit 1
  fi
  if "$VENV_PY" - <<PY
import json, urllib.request
url = "http://${COPLAND_AGENT_HOST}:${COPLAND_AGENT_PORT}/api/health"
try:
    with urllib.request.urlopen(url, timeout=1) as r:
        data = json.load(r)
    # Require current agent shape so a stale process cannot pass the gate.
    ok = (
        data.get("ok") is True
        and data.get("service") == "copland-agent"
        and "seed_dir" in data
        and "mscore_available" in data
    )
    raise SystemExit(0 if ok else 1)
except Exception:
    raise SystemExit(1)
PY
  then
    ready=1
    break
  fi
  sleep 0.2
done

if [[ "$ready" != "1" ]]; then
  echo "Agent failed health check within timeout" >&2
  exit 1
fi

echo "Agent healthy; starting UI on :${PORT} (proxy → ${COPLAND_AGENT_URL})"
cd "$ROOT"
exec node server.mjs
