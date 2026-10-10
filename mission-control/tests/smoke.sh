#!/usr/bin/env bash
# smoke.sh — the quick version: the backend starts, answers, and refuses politely.
#
#   bash mission-control/tests/smoke.sh          # ~10 s
#   MIRAI_TEST_PORT=8811 bash .../smoke.sh       # if you want to fix the port
#
# It runs against a throwaway HOME (/tmp/fakehome) built fresh by fixture.sh, on
# its own port, so it never touches a real crew or your Mac's state. Use prove.sh
# for the full pass.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
export HOME=/tmp/fakehome
export MIRAI_DIR=/tmp/fakehome/mirai
export MIRAI_KANBAN=off
# A test run must leave the tree as it found it: no __pycache__ beside the modules.
export PYTHONDONTWRITEBYTECODE=1

# A throwaway crew every run: /tmp does not survive a reboot, and a missing
# ~/.hermes would make this pass look like a failure.
mkdir -p /tmp/fakehome
bash "$HERE/tests/fixture.sh" >/dev/null || exit 1
cd "$HERE/server" || exit 1

# Its own port, and a free one if the fixed one is taken by whatever else is open.
PORT="${MIRAI_TEST_PORT:-8801}"
# SO_REUSEADDR mirrors what the server itself sets: without it, a port left in
# TIME_WAIT by the previous run reads as "busy" and the test silently moves.
if ! python3 - "$PORT" <<'PYPORT'
import socket, sys
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    sys.exit(1)
finally:
    s.close()
PYPORT
then
  PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
  echo "(8801 was busy: this run uses $PORT)"
fi

python3 server.py "$PORT" > /tmp/srv.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
sleep 1.5
echo "=== smoke: port $PORT, HOME $HOME ==="

echo "--- ping ---"
curl -s "localhost:$PORT/api/ping"
echo
echo "--- settings (operator_name from USER.md) ---"
curl -s "localhost:$PORT/api/settings"
echo
echo "--- 405 with Allow ---"
curl -s -i -X POST "localhost:$PORT/api/ping" | sed -n '1p;/Allow/p'
echo "--- settings POST valid ---"
curl -s -X POST "localhost:$PORT/api/settings" -d '{"settings":{"display_name":"Afrizal","timezone":"Asia/Jakarta"}}'
echo
echo "--- refusals ---"
curl -s -X POST "localhost:$PORT/api/settings" -d '{"operator_name":"x"}'; echo
curl -s -X POST "localhost:$PORT/api/settings" -d '{"voice_engine":"banana"}'; echo
curl -s -X POST "localhost:$PORT/api/settings" -d 'not json'; echo
curl -s -X POST "localhost:$PORT/api/settings" -d '[1,2]'; echo
curl -s -X POST "localhost:$PORT/api/settings" -d "{\"display_name\":\"$(printf 'a%.0s' {1..30})\"}"; echo
echo "--- agents ---"
curl -s "localhost:$PORT/api/agents" > /tmp/agents.json
python3 - <<'PY'
import json
d = json.load(open("/tmp/agents.json"))
agents = d.get("agents") or []
if not agents:
    raise SystemExit("FAIL: the fixture produced no agents — check tests/fixture.sh")
for a in agents:
    s = a["stats"]
    print(f"{a['code']:3} {a['name']:12} {a['profile']:10} {a['model']:18} {a['status']:12} "
          f"sess={s['sessions_total']} 24h={s['sessions_24h']} avg={s['avg_response_s']}")
f = d["fleet"]
print("fleet:", {k: f[k] for k in ("seats", "working_now", "active_today", "sessions_total", "sessions_24h")})
print("aliases present:", all(a.get("aliases") for a in agents))
print("hourly keys:", list(agents[0]["stats"]["hourly_24h"].keys()))
PY
export SMOKE_PORT="$PORT"
echo "--- cache check ---"
python3 - <<'PY'
import json, urllib.request, os
port = os.environ.get("SMOKE_PORT")
a = json.load(urllib.request.urlopen(f"http://localhost:{port}/api/agents"))
b = json.load(urllib.request.urlopen(f"http://localhost:{port}/api/agents"))
c = json.load(urllib.request.urlopen(f"http://localhost:{port}/api/agents?force=1"))
print("same generated_at (from cache, <2s):", a["generated_at"] == b["generated_at"])
print("force bypasses cache:", c["generated_at"] != a["generated_at"])
PY

echo "--- server log tail ---"
tail -5 /tmp/srv.log
