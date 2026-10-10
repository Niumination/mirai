#!/usr/bin/env bash
# prove.sh — the proof the pack asks for (Prompt 33), and it is a script so it can
# be re-run rather than trusted: every GET, then the refusals, then the page and
# /lib, then the mission lifecycle and the terminal.
#
#   bash mission-control/tests/prove.sh
#
# It runs against a throwaway HOME (/tmp/fakehome) and its own port (8802), so it
# never touches a real crew. Hermes is not required: the fixture creates a fake
# ~/.hermes, which is why the board reads "local" and the voice engine is absent.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE/server" || exit 1
export HOME=/tmp/fakehome
export MIRAI_DIR=/tmp/fakehome/mirai
export MIRAI_KANBAN=off
# A test run must leave the tree as it found it: no __pycache__ beside the modules.
export PYTHONDONTWRITEBYTECODE=1
rm -rf /tmp/fakehome/mirai

# A throwaway crew, built here so this script is the only thing you have to run:
# /tmp does not survive a reboot, and without a ~/.hermes the fleet reads empty.
mkdir -p /tmp/fakehome
bash "$HERE/tests/fixture.sh" >/dev/null || exit 1

python3 server.py 8802 > /tmp/prove.log 2>&1 &
SRV=$!
sleep 2

printf '%-46s ' "GET /api/ping";            curl -s localhost:8802/api/ping; echo
printf '%-46s ' "GET /api/agents";          curl -s localhost:8802/api/agents | head -c 80; echo
printf '%-46s ' "GET /api/settings";        curl -s localhost:8802/api/settings; echo
printf '%-46s ' "GET /api/health";          curl -s localhost:8802/api/health | python3 -c "import json,sys; d=json.load(sys.stdin); print('ok=',d['ok'],'cpu=',d['cpu']['pct'],'mem%',d['memory']['pct'],'diag=',d['diagnostics']['status'],'checks=',d['diagnostics']['checks'],'/',d['diagnostics']['passed'])"
printf '%-46s ' "GET /api/traffic";         curl -s localhost:8802/api/traffic; echo
printf '%-46s ' "GET /api/missions";        curl -s localhost:8802/api/missions | head -c 120; echo
printf '%-46s ' "GET /api/cron";            curl -s localhost:8802/api/cron; echo
printf '%-46s ' "GET /api/docs";            curl -s localhost:8802/api/docs | head -c 80; echo
printf '%-46s ' "GET /api/files/tree";      curl -s localhost:8802/api/files/tree | head -c 110; echo
printf '%-46s ' "GET /api/terminal/list";   curl -s localhost:8802/api/terminal/list; echo
printf '%-46s ' "GET /api/avatars/library"; curl -s localhost:8802/api/avatars/library; echo
printf '%-46s ' "GET /api/voice/config";    curl -s localhost:8802/api/voice/config | head -c 110; echo
printf '%-46s ' "GET /api/chat/history";    curl -s "localhost:8802/api/chat/history?agent=EX&limit=5"; echo
printf '%-46s ' "GET /api/models";          curl -s localhost:8802/api/models | head -c 110; echo
printf '%-46s ' "GET /api/terminal/commands"; curl -s localhost:8802/api/terminal/commands; echo
printf '%-46s ' "GET /api/workforce/team";  curl -s localhost:8802/api/workforce/team | head -c 110; echo
printf '%-46s ' "GET /api/workforce/library"; curl -s localhost:8802/api/workforce/library | head -c 80; echo

echo
echo "=== REFUSALS (must all be our JSON error) ==="
printf '%-46s ' "bad mission action";   curl -s -X POST localhost:8802/api/missions/action -d '{"id":"NX-1001","action":"bogus"}'; echo
printf '%-46s ' "path traversal id";    curl -s -X POST localhost:8802/api/missions/action -d '{"id":"../../etc/passwd","action":"stop"}'; echo
printf '%-46s ' "files .. path";        curl -s "localhost:8802/api/files/read?agent=EX&path=../etc/passwd"; echo
printf '%-46s ' "avatars .. name";      curl -s "localhost:8802/api/avatars/file?name=../../etc/passwd"; echo
printf '%-46s ' "unknown setting key";  curl -s -X POST localhost:8802/api/settings -d '{"nonsense":"x"}'; echo
printf '%-46s ' "wrong remove confirm"; curl -s -X POST localhost:8802/api/workforce/remove -d '{"code":"EX","confirm":"WRONG NAME"}'; echo
printf '%-46s ' "chat no agent";        curl -s -X POST localhost:8802/api/chat -d '{"text":"hi"}'; echo
printf '%-46s ' "docs bad id";          curl -s "localhost:8802/api/docs/read?id=../../etc/passwd"; echo
printf '%-46s ' "terminal bad runtime"; curl -s -X POST localhost:8802/api/terminal/open -d '{"runtime":"powershell"}'; echo
printf '%-46s ' "cron bad action";      curl -s -X POST localhost:8802/api/cron/action -d '{"agent":"default","id":"x","action":"explode"}'; echo
printf '%-46s ' "body too large";       curl -s -o /dev/null -w '%{http_code} ' -X POST localhost:8802/api/settings -H 'Content-Length: 31000000' -d ''; echo

echo
echo "=== DOCS ROUNDTRIP ==="
curl -s -X POST localhost:8802/api/docs/save -d '{"title":"Test document","text":"# Hello\n\nBody here.","agent":"EX"}' | head -c 140; echo
curl -s -X POST localhost:8802/api/docs/from-chat -d '{"agent":"RE","text":"Chat reply text"}' | head -c 120; echo
curl -s localhost:8802/api/docs | python3 -c "import json,sys; d=json.load(sys.stdin); print('docs:', [(x['id'],x['status']) for x in d['documents']])"

echo
echo "=== MISSION LIFECYCLE (no board: local mode) ==="
MID=$(curl -s -X POST localhost:8802/api/missions -d '{"name":"Riset kopi gayo","objective":"Find three sources on Gayo arabica prices","max_steps":2,"time_limit_min":15}' | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
echo "created: $MID"
sleep 3
curl -s localhost:8802/api/missions | python3 -c "
import json,sys
d=json.load(sys.stdin); m=[x for x in d['missions']][0]
print('status:', m['status'], '| steps:', [(s['idx'], s['agent'], s['title'][:38], s['status']) for s in m['steps']])
print('limits object:', d['limits'])
"
echo "approve:"; curl -s -X POST localhost:8802/api/missions/action -d "{\"id\":\"$MID\",\"action\":\"approve\"}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(' action=',d.get('action'),'cards=',d.get('cards'),'mode=',d.get('mode'),'status=',d['mission']['status'])"
sleep 2
echo "cancel:"; curl -s -X POST localhost:8802/api/missions/action -d "{\"id\":\"$MID\",\"action\":\"cancel\"}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(' status=',d['mission']['status'],'events=',[e['kind'] for e in d['mission']['events']])"
echo "clear:"; curl -s -X POST localhost:8802/api/missions/action -d "{\"id\":\"$MID\",\"action\":\"clear\"}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(' cleared_at set:', bool(d['mission']['cleared_at']))"

echo
echo "=== TERMINAL ==="
SID=$(curl -s -X POST localhost:8802/api/terminal/open -d '{"runtime":"bash","cols":80,"rows":24}' | python3 -c "import json,sys; print(json.load(sys.stdin)['session']['id'])")
echo "session: $SID"
curl -s -X POST localhost:8802/api/terminal/input -d "{\"id\":\"$SID\",\"data\":\"echo MIRAI_OK\\n\"}" >/dev/null
sleep 1
curl -s -N --max-time 2 "localhost:8802/api/terminal/stream?id=$SID" | head -c 300 | tr -d '\n' | sed 's/^/stream head: /'
echo
curl -s -X POST localhost:8802/api/terminal/close -d "{\"id\":\"$SID\"}"; echo

echo
echo "=== THE PAGE AND /lib (prompt 34/35 wiring) ==="
mkdir -p /tmp/fakehome/mirai/lib/mediapipe
printf '<!doctype html><title>dash</title>hello from the page' > /tmp/fakehome/mirai/dashboard.html
printf 'export const x=1;\n' > /tmp/fakehome/mirai/lib/mediapipe/vision_bundle.mjs
head -c 4096 /dev/zero | tr '\0' 'M' > /tmp/fakehome/mirai/lib/mediapipe/hand_landmarker.task
printf '%-46s ' "GET / page, bytes match disk"; curl -s -o /tmp/page.html -w '%{http_code} ' localhost:8802/; wc -c < /tmp/page.html | tr -d ' '; printf ' vs disk '; wc -c < /tmp/fakehome/mirai/dashboard.html
printf '%-46s ' "GET / gzip (smaller)";   curl -s -H 'Accept-Encoding: gzip' -o /tmp/page.gz -w '%{http_code} ' localhost:8802/; wc -c < /tmp/page.gz
ET=$(curl -s -D - -o /dev/null localhost:8802/ | grep -i '^etag' | tr -d '\r' | cut -d' ' -f2)
printf '%-46s ' "GET / If-None-Match 304"; curl -s -o /dev/null -w '%{http_code}\n' -H "If-None-Match: $ET" localhost:8802/
printf '%-46s ' "GET /index.html same page"; curl -s -o /dev/null -w '%{http_code} %{size_download}\n' localhost:8802/index.html
printf '%-46s ' "GET /lib/vision_bundle.mjs"; curl -s -o /dev/null -w '%{http_code} %{content_type}\n' localhost:8802/lib/mediapipe/vision_bundle.mjs
printf '%-46s ' "GET /lib/hand_landmarker.task"; curl -s -o /dev/null -w '%{http_code} %{content_type}\n' localhost:8802/lib/mediapipe/hand_landmarker.task
printf '%-46s ' "GET /lib traversal (--path-as-is)"; curl -s --path-as-is "localhost:8802/lib/../../mission-control/server/server.py"; echo

echo
echo "=== SETTINGS: the pack's own refusals (prompt 14) ==="
printf '%-46s ' "bare object accepted";  curl -s -X POST localhost:8802/api/settings -d '{"display_name":"Bare"}'; echo
printf '%-46s ' "30-char display_name";  curl -s -X POST localhost:8802/api/settings -d '{"settings":{"display_name":"012345678901234567890123456789"}}'; echo
printf '%-46s ' "voice_engine banana";   curl -s -X POST localhost:8802/api/settings -d '{"settings":{"voice_engine":"banana"}}'; echo
printf '%-46s ' "body not JSON";         curl -s -X POST localhost:8802/api/settings -d 'not json at all'; echo
printf '%-46s ' "body is a JSON array";  curl -s -X POST localhost:8802/api/settings -d '[1,2,3]'; echo
printf '%-46s ' "operator_name";         curl -s -X POST localhost:8802/api/settings -d '{"settings":{"operator_name":"x"}}'; echo
printf '%-46s ' "unknown key";           curl -s -X POST localhost:8802/api/settings -d '{"settings":{"nonsense":1}}'; echo
printf '%-46s ' "real 32 MB body";       head -c 32000000 /dev/zero | tr '\0' 'a' > /tmp/big.bin; curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:8802/api/settings --data-binary @/tmp/big.bin

echo
echo "=== 405 / 404 shape ==="
curl -s -i -X POST localhost:8802/api/ping | sed -n '1p;/Allow/p'
curl -s localhost:8802/api/nothing; echo


echo
echo "=== THE GATE (prompt 43): four states, page AND api ==="
# A second instance, same throwaway HOME, its own port, MIRAI_AUTH=on. The token is
# written by the gate itself into <data>/auth.token with mode 0600.
python3 - <<'PYGATE'
import os, pathlib, secrets
d = pathlib.Path("/tmp/fakehome/mirai/data"); d.mkdir(parents=True, exist_ok=True)
t = d / "auth.token"
if not t.exists():
    t.write_text(secrets.token_urlsafe(32) + "\n")
    os.chmod(t, 0o600)
PYGATE
TOKEN="$(tr -d '\n' < /tmp/fakehome/mirai/data/auth.token)"
MIRAI_AUTH=on python3 -u server.py 8803 > /tmp/prove-gate.log 2>&1 &
GSRV=$!
sleep 2
say() { printf '%-46s ' "$1"; }

say "1. gate ON, page without a token"
printf '%s ' "$(curl -s -o /tmp/gate-page.html -w '%{http_code}' localhost:8803/)"; grep -c "The door is" /tmp/gate-page.html
say "   ...and it is NOT the dashboard"
grep -c "mirai" /tmp/gate-page.html | sed 's/^/  signin page mentions: /'

say "2. gate ON, api without a token"
curl -s -o /dev/null -w '%{http_code} ' localhost:8803/api/agents; curl -s localhost:8803/api/agents; echo

say "3a. right token, X-Auth-Token header"
curl -s -o /dev/null -w '%{http_code} ' -H "X-Auth-Token: $TOKEN" localhost:8803/api/agents
curl -s -o /dev/null -w '%{http_code}\n' -H "X-Auth-Token: $TOKEN" localhost:8803/

say "3b. right token, Bearer header"
curl -s -o /dev/null -w '%{http_code} ' -H "Authorization: Bearer $TOKEN" localhost:8803/api/agents
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" localhost:8803/

say "3c. the one-tap link sets a cookie"
curl -s -D /tmp/gate-head.txt -o /dev/null -c /tmp/gate-jar.txt "localhost:8803/?k=$TOKEN"
grep -ci "set-cookie: mirai_auth=.*HttpOnly" /tmp/gate-head.txt
grep -ci "set-cookie" /tmp/gate-head.txt | sed "s/^/  set-cookie headers on the link: /"
say "   ...the cookie alone opens api and page"
curl -s -o /dev/null -w '%{http_code} ' -b /tmp/gate-jar.txt localhost:8803/api/agents
curl -s -o /dev/null -w '%{http_code}\n' -b /tmp/gate-jar.txt localhost:8803/

say "4. wrong token"
curl -s -o /dev/null -w '%{http_code} ' -H "X-Auth-Token: nope" localhost:8803/api/agents
curl -s -o /dev/null -w '%{http_code} ' "localhost:8803/?k=nope"
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer nope" localhost:8803/api/agents

say "5. /api/ping stays open (uptime checks must not go red)"
curl -s -o /dev/null -w '%{http_code}\n' localhost:8803/api/ping

say "6. the token file"
stat -c '%a %n' /tmp/fakehome/mirai/data/auth.token 2>/dev/null || ls -l /tmp/fakehome/mirai/data/auth.token

say "7. THE LOG: the ?k= link must not be written down"
if grep -q "$TOKEN" /tmp/prove-gate.log; then echo "LEAKED"; else echo "no token in the log"; fi
grep -c "redacted" /tmp/prove-gate.log

kill $GSRV 2>/dev/null

echo
echo "=== THE HOST ALLOWLIST (prompt 42: nothing but the names we answer to) ==="
printf '%-46s ' "a foreign Host on the open server"
curl -s -o /dev/null -w '%{http_code} ' -H 'Host: evil.example' localhost:8802/api/agents
curl -s -H 'Host: evil.example' localhost:8802/api/agents; echo
printf '%-46s ' "a tailnet name, once MIRAI_HOSTS names it"
MIRAI_HOSTS=mac.tailnet.ts.net python3 -u server.py 8804 > /tmp/prove-hosts.log 2>&1 &
HSRV=$!
sleep 1.5
curl -s -o /dev/null -w '%{http_code} ' -H 'Host: mac.tailnet.ts.net' localhost:8804/api/agents
curl -s -o /dev/null -w '%{http_code} (evil on the same instance)\n' -H 'Host: evil.example' localhost:8804/api/agents
kill $HSRV 2>/dev/null

kill $SRV 2>/dev/null
echo
echo "=== SERVER LOG (any tracebacks?) ==="
grep -c "Traceback" /tmp/prove.log || true
tail -3 /tmp/prove.log
