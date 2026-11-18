#!/usr/bin/env bash
# A private Ollama server for this project on 127.0.0.1:11435, so these settings never touch the
# Ollama app on :11434. Shares the app's model store. Cloud features are off.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export OLLAMA_HOST=127.0.0.1:11435 OLLAMA_NO_CLOUD=1 OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-2}"
export OLLAMA_MAX_LOADED_MODELS=2 OLLAMA_KEEP_ALIVE=30m
ollama serve &
PID=$!; trap 'kill $PID' EXIT
until curl -sf http://127.0.0.1:11435/api/version >/dev/null; do sleep 0.3; done
ollama create mirofish-qwen -f "$ROOT/ollama/Modelfile" >/dev/null
echo "ollama ready on 127.0.0.1:11435 (slots: $OLLAMA_NUM_PARALLEL)"
wait $PID
