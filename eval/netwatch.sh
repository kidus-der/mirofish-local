#!/bin/bash
# Samples every process in the backend tree, plus the project's Ollama, for non-loopback sockets.
# Writes one line per sample; any line starting with LEAK is a connection that left the machine.
out="$1"; root_pattern="${2:-python run.py}"
while true; do
  pids=$(pgrep -f "$root_pattern"; pgrep -f "run_(parallel|twitter|reddit)_simulation"; pgrep -f "redislite/bin/redis-server"; lsof -nP -iTCP:11435 -sTCP:LISTEN -t 2>/dev/null)
  list=$(echo $pids | tr ' ' ',')
  hits=""
  [ -n "$list" ] && hits=$(lsof -nP -a -p "$list" -i 2>/dev/null | awk 'NR>1 && $0 !~ /127\.0\.0\.1|\[::1\]|localhost|\*:/')
  if [ -n "$hits" ]; then echo "LEAK +${SECONDS}s $hits" >> "$out"; else echo "ok +${SECONDS}s procs=$(echo $pids | wc -w)" >> "$out"; fi
  sleep 5
done
