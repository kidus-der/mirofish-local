#!/usr/bin/env bash
# Checks the local-only protections on this machine. It sends no project data anywhere.
# The two outbound attempts run inside the sandbox and are expected to be refused.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
fails=0
pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; fails=$((fails + 1)); }
skip() { printf 'SKIP  %s\n' "$1"; }
py() { (cd backend && env -u PYTHONPATH PYTHONPATH=. uv run --frozen --offline python "$@"); }

out=$(scripts/run-sandboxed.sh curl -v -m 8 http://1.1.1.1 2>&1 || true)
if printf '%s' "$out" | grep -qi "not permitted"; then pass "Sandbox refuses a direct internet address"
else fail "Sandbox refuses a direct internet address"; fi

if scripts/run-sandboxed.sh curl -s -m 8 https://example.com >/dev/null 2>&1; then fail "Sandbox refuses a website"
else pass "Sandbox refuses a website"; fi

port=18765
python3 -m http.server "$port" --bind 127.0.0.1 --directory "$ROOT/scripts" >/dev/null 2>&1 &
server=$!
sleep 1
if scripts/run-sandboxed.sh curl -sf -m 5 "http://127.0.0.1:$port/" >/dev/null 2>&1; then pass "Sandbox still allows this machine's loopback"
else fail "Sandbox still allows this machine's loopback"; fi
kill "$server" 2>/dev/null
wait "$server" 2>/dev/null

out=$(py -c "import socket; socket.create_connection(('1.1.1.1', 80), 2)" 2>&1)
if [ $? -ne 0 ] && printf '%s' "$out" | grep -q netguard; then pass "Python network guard blocks outside sockets"
else fail "Python network guard blocks outside sockets"; fi

if py -c "from netguard import host_allowed as h; raise SystemExit(0 if h('127.0.0.1') and not h('api.openai.com') else 1)" >/dev/null 2>&1
then pass "App accepts only local model addresses"
else fail "App accepts only local model addresses"; fi

if (cd backend && env -u PYTHONPATH uv run --frozen --offline pytest -q tests/test_local_only.py) >/dev/null 2>&1
then pass "Local-only test suite"
else fail "Local-only test suite"; fi

running=0
for p in 3000 5001 11435; do
  listeners=$(lsof -nP -iTCP:"$p" -sTCP:LISTEN 2>/dev/null | awk 'NR>1 {print $9}')
  [ -n "$listeners" ] || continue
  running=1
  if printf '%s\n' "$listeners" | grep -qvE '^(127\.0\.0\.1|\[::1\]|localhost):'; then fail "Port $p listens only on loopback"
  else pass "Port $p listens only on loopback"; fi
done

pids=$( (pgrep -f "python run.py"; pgrep -f "run_(parallel|twitter|reddit)_simulation"; pgrep -f "redislite/bin/redis-server"; lsof -tiTCP:11435 -sTCP:LISTEN) 2>/dev/null | sort -u | paste -sd, -)
if [ "$running" -eq 1 ] && [ -n "$pids" ]; then
  outside=$(lsof -nP -a -p "$pids" -i 2>/dev/null | awk 'NR>1 && $0 !~ /127\.0\.0\.1|\[::1\]|localhost|\*:/')
  if [ -z "$outside" ]; then pass "Running services have no outside connections"
  else fail "Running services have no outside connections"; fi
else
  skip "Running-service checks (start the app, then run this again)"
fi

echo
if [ "$fails" -eq 0 ]; then echo "All local-only checks passed."; else echo "$fails check(s) failed."; exit 1; fi
