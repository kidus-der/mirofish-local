#!/usr/bin/env bash
# One-time setup for MiroFish Local. This is the only step that needs the internet.
# Safe to run again: finished steps are reused.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing '$1'. $2" >&2; exit 1; }; }
[ "$(uname -s)" = "Darwin" ] || { echo "This setup supports macOS only, because its network sandbox uses sandbox-exec." >&2; exit 1; }
need uv "Install it from https://docs.astral.sh/uv/"
need node "Install Node.js 18 or newer from https://nodejs.org/"
need npm "It is included with Node.js."
need ollama "Install it from https://ollama.com/download"
need curl "It is included with macOS."

echo "==> Creating local settings"
[ -f .env ] || cp .env.example .env

echo "==> Installing web dependencies"
npm ci
npm ci --prefix frontend

echo "==> Installing Python dependencies"
(cd backend && uv sync --frozen)

echo "==> Downloading offline model files into backend/.models"
(cd backend && PYTHONPATH="$PWD" uv run --frozen python ../scripts/bootstrap-offline.py)

echo "==> Downloading Ollama models"
export OLLAMA_HOST=127.0.0.1:11435
ollama serve >/dev/null 2>&1 &
OLLAMA_PID=$!
trap 'kill "$OLLAMA_PID" 2>/dev/null || true' EXIT
for _ in $(seq 1 60); do
  curl -sf "http://$OLLAMA_HOST/api/version" >/dev/null && break
  sleep 0.5
done
curl -sf "http://$OLLAMA_HOST/api/version" >/dev/null || { echo "Ollama did not start on $OLLAMA_HOST." >&2; exit 1; }
ollama pull qwen3.5:9b-q4_K_M
ollama pull qwen3-embedding:0.6b
ollama create mirofish-qwen -f ollama/Modelfile

echo
echo "Setup complete. Start MiroFish Local with: ./scripts/start.sh"
