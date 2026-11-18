#!/usr/bin/env bash
# Starts the private model server, sandboxed backend and web app, and keeps the Mac awake.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

[ -f .env ] && [ -d backend/.venv ] && [ -d node_modules ] && [ -d backend/.models ] || {
  echo "Run ./scripts/setup.sh first." >&2; exit 1; }
for port in 3000 5001 11435; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use. Stop that program and try again." >&2; exit 1
  fi
done

./scripts/serve-ollama.sh &
OLLAMA_PID=$!
trap 'kill "$OLLAMA_PID" 2>/dev/null || true' EXIT INT TERM
for _ in $(seq 1 240); do
  curl -sf http://127.0.0.1:11435/api/tags 2>/dev/null | grep -q mirofish-qwen && break
  kill -0 "$OLLAMA_PID" 2>/dev/null || { echo "The model server stopped during startup." >&2; exit 1; }
  sleep 0.5
done
curl -sf http://127.0.0.1:11435/api/tags | grep -q mirofish-qwen || { echo "The model server did not become ready." >&2; exit 1; }

echo "Open http://localhost:3000 when the web app is ready. Press Ctrl+C to stop everything."
caffeinate -ims npm run dev
