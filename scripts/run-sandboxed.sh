#!/bin/bash
# OS-level enforcement of the local-only rule: run a command (default: the backend) under macOS
# sandbox-exec with outbound network denied except loopback TCP and unix sockets. netguard.py only
# covers Python's socket module; this also stops raw _socket, ctypes, and any child binary.
# NOTE: sandbox-exec is deprecated by Apple (no replacement for CLI use) but still functional.
# Ollama is NOT sandboxed: it runs separately and is reached over loopback.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE='(version 1)
(allow default)
(deny network-outbound)
(allow network-outbound (remote tcp "localhost:*"))
(allow network-outbound (remote unix-socket))'
if [ "$#" -eq 0 ]; then
  cd "$ROOT/backend"
  set -- uv run --frozen --offline python run.py
fi
exec sandbox-exec -p "$PROFILE" "$@"
