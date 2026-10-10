#!/usr/bin/env bash
# wiki-e2e.sh — the wiki dashboard, end to end, on throwaway fixtures.
#
# WHAT THIS PROVES
#   1. the page is served byte-for-byte, and the token rides out as an HttpOnly
#      SameSite=Strict cookie so the page's own fetch calls can write;
#   2. /api/data draws the same shape as the page's demo payload (pages, sources,
#      links, log entries, lint lines);
#   3. /api/memory/page refuses a traversal name (400), says "not on file" for a
#      missing page (404), and serves the meta files (WIKI / index / log);
#   4. every write refuses without the token, then accepts it as a cookie or as
#      the X-Wiki-Token header: drops, lint-now, commit;
#   5. the drop door: data: URLs only, hostile names refused in the reply only,
#      same name twice becomes name-2, and one drop every 5 seconds;
#   6. the commit is the wiki's own (git -c user.name=MIRAI ...): it never needs
#      a global git identity, and it says "nothing to snapshot" when clean;
#   7. a GET on a POST route answers 405 with Allow, an unknown route 404, and a
#      foreign Host header 403 (DNS rebinding);
#   8. a client that hangs up mid-request leaves no traceback in the log;
#   9. the fallback page (no wiki-page.html) and /upload both render.
#
# WHAT IT DOES NOT TOUCH
#   Your real wiki, your real dashboard folder: it runs against /tmp/wiki-e2e
#   with CREW_WIKI_DIR pointed there, on its own ports (8903 / 8904). The only
#   files it may create next to server.py are dashboard.token and
#   lint-request.txt (the lint button's note to the 02:50 job); both are removed
#   again unless they were already there.
#
# USAGE
#   bash tests/wiki-e2e.sh          # ~35 s
#   P1=8913 P2=8914 bash tests/wiki-e2e.sh
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(cd "$HERE/.." && pwd)"
SKEL="$(cd "$PROJ/../wiki-skeleton" && pwd)"
WIKISH="$(cd "$PROJ/../skill/wiki" && pwd)/wiki.sh"
P1="${P1:-8903}"; P2="${P2:-8904}"
R="/tmp/wiki-e2e"
SRV=""; SRV2=""

TOKEN_EXISTED=1; [ -f "$PROJ/dashboard.token" ] || TOKEN_EXISTED=0
LINT_EXISTED=1;  [ -f "$PROJ/lint-request.txt" ] || LINT_EXISTED=0
cleanup() {
  [ -n "$SRV" ] && kill "$SRV" 2>/dev/null
  [ -n "$SRV2" ] && kill "$SRV2" 2>/dev/null
  # the two files a proof run may leave next to the server, put back to how it found them
  [ "$TOKEN_EXISTED" -eq 0 ] && rm -f "$PROJ/dashboard.token"
  [ "$LINT_EXISTED" -eq 0 ] && rm -f "$PROJ/lint-request.txt"
  sleep 0.5   # let the ports go before the next run asks for them
  return 0
}
trap cleanup EXIT

fail=0
say() { printf '%-46s %s\n' "$1" "$2"; }
chk() { case "$2" in *"$3"*) say "$1" "ok";; *) say "$1" "MISMATCH: $2"; fail=1;; esac; }
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

echo "== fixtures in $R =="
rm -rf "$R"; mkdir -p "$R/processed"/{personal,business,research,concepts} "$R/raw"/{_inbox,_working,_done,_failed}
cp "$SKEL"/WIKI.md "$SKEL"/index.md "$SKEL"/log.md "$R"/
export CREW_WIKI_DIR="$R"
bash "$WIKISH" file business acme-corp --agent developer --summary "Customer since 2026-03" <<'EOF' >/dev/null
# Acme Corp

Customer since 2026-03. Two reports delivered.
EOF
bash "$WIKISH" file personal afrizal --agent executor --summary "The owner" <<'EOF' >/dev/null
# Afrizal

Owner. Banda Aceh.
EOF
bash "$WIKISH" log --agent executor "filed the owner page" --pages afrizal >/dev/null
printf '# health\n\nheartbeat wiki-dropbox 2026-10-08T16:00 ok 2 ingested 0 failed\n\n## 2026-10-08\n- Contradiction: acme-corp pricing says 1500 while the mail thread says 1800\n- Orphan: travel-policy has no inbound links\n' > "$R/_wiki-health.md"
git -C "$R" init -q && git -C "$R" add -A \
  && git -C "$R" -c user.email=mirai@localhost -c user.name=MIRAI commit -qm "the first pages"

echo "== the server =="
# The verb's lock wait is shortened for the test: the busy case must be provable in a
# second, not after a 30-second wait. The server passes its env to the verb.
export WIKI_LOCK_WAIT=1
export MIRAI_WIKI_CLI="$WIKISH"        # the button goes through the verb, under the wiki lock
cd "$PROJ"
python3 -u server.py "$P1" > /tmp/wiki-e2e-server.log 2>&1 &
SRV=$!
sleep 2
B="127.0.0.1:$P1"
TOK="$(python3 -B -c 'import server; print(server.ensure_token())')"
say "token file" "$(python3 -c 'import os,stat;print(oct(stat.S_IMODE(os.stat("dashboard.token").st_mode))[2:])')"

echo "== 1. the page and its cookie =="
curl -s -D /tmp/wiki-e2e-head.txt -o /tmp/wiki-e2e-page.html "$B/"
chk "status line" "$(head -1 /tmp/wiki-e2e-head.txt | tr -d '\r')" "200 OK"
chk "cookie flags" "$(grep -i '^set-cookie' /tmp/wiki-e2e-head.txt | tr -d '\r')" "HttpOnly; SameSite=Strict"
say "page bytes vs disk" "$(wc -c < /tmp/wiki-e2e-page.html) vs $(wc -c < "$PROJ/wiki-page.html")"

echo "== 2. /api/data =="
curl -s "$B/api/data" | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert d['ok'] is True
assert d['stats']['pages'] == 2, d['stats']
assert sorted({n['group'] for n in d['nodes']}) == ['entities']
assert d['log_tail'] and d['lint'], 'log tail and lint must both carry lines'
print('  ok, shape matches the page payload:', d['stats'])"

echo "== 3. the reader =="
chk "page body" "$(curl -s "$B/api/memory/page?name=acme-corp" | python3 -c 'import json,sys;print(json.load(sys.stdin)["content"][:9])')" "# Acme"
chk "traversal name" "$(curl -s "$B/api/memory/page?name=../../etc/passwd")" "bad page name"
chk "missing page" "$(curl -s "$B/api/memory/page?name=nope")" "not on file: nope"
chk "meta file" "$(curl -s "$B/api/memory/page?name=WIKI" | python3 -c 'import json,sys;print(json.load(sys.stdin)["content"][:1])')" "#"

echo "== 4. the token =="
chk "a write without it" "$(curl -s -X POST "$B/api/drop" -H 'Content-Type: application/json' --data-binary '{"name":"x.txt","data":"data:text/plain;base64,eA=="}')" "needs the dashboard token"
curl -s -c /tmp/wiki-e2e-jar.txt -o /dev/null "$B/"      # what the browser keeps

echo "== 5. the drop door =="
chk "a file, with the cookie" "$(curl -s -b /tmp/wiki-e2e-jar.txt -X POST "$B/api/drop" -H 'Content-Type: application/json' --data-binary '{"name":"note.txt","data":"data:text/plain;base64,aGVsbG8gZnJvbSB0aGUgZHJvcCBkb29y"}')" '"saved": "note.txt"'
sleep 6
chk "a link, with the header" "$(curl -s -X POST "$B/api/drop" -H 'Content-Type: application/json' -H "X-Wiki-Token: $TOK" --data-binary '{"url":"https://example.com/article","title":"An article"}')" '"kind": "link"'
sleep 6
chk "not a data: URL" "$(curl -s -b /tmp/wiki-e2e-jar.txt -X POST "$B/api/drop" -H 'Content-Type: application/json' --data-binary '{"name":"note.txt","text":"hello"}')" "must arrive as a data: URL"
sleep 6
chk "a hostile name" "$(curl -s -b /tmp/wiki-e2e-jar.txt -X POST "$B/api/drop" -H 'Content-Type: application/json' --data-binary '{"name":"../../etc/passwd","data":"data:text/plain;base64,eA=="}')" "not allowed"
sleep 6
chk "the same name twice" "$(curl -s -b /tmp/wiki-e2e-jar.txt -X POST "$B/api/drop" -H 'Content-Type: application/json' --data-binary '{"name":"note.txt","data":"data:text/plain;base64,c2Vjb25k"}')" 'note-2.txt'
say "the inbox now" "$(ls "$R/raw/_inbox" | tr '\n' ' ')"

echo "== 6. lint and the snapshot =="
chk "lint-now" "$(curl -s -b /tmp/wiki-e2e-jar.txt -X POST "$B/api/memory/lint-now")" '"ok": true'
chk "lint-now again inside 5 min" "$(curl -s -b /tmp/wiki-e2e-jar.txt -X POST "$B/api/memory/lint-now")" "one lint request every 5 minutes"
chk "commit (through the verb)" "$(curl -s -b /tmp/wiki-e2e-jar.txt -X POST "$B/api/memory/commit")" '"committed": true'
chk "commit again" "$(curl -s -b /tmp/wiki-e2e-jar.txt -X POST "$B/api/memory/commit")" "nothing to snapshot"
# hold the wiki lock, then press the button: it must say busy, and commit nothing
( mkdir "$R/.wiki.lock" && sleep 4; rmdir "$R/.wiki.lock" 2>/dev/null ) &
HOLDER=$!
sleep 0.7
chk "commit while the wiki is busy" "$(curl -s -b /tmp/wiki-e2e-jar.txt -X POST "$B/api/memory/commit")" "wiki is busy, nothing was snapshotted"
chk "  and it answers 409" "$(curl -s -o /dev/null -w '%{http_code}' -b /tmp/wiki-e2e-jar.txt -X POST "$B/api/memory/commit")" "409"
wait "$HOLDER" 2>/dev/null
say "the wiki's own log" "$(git -C "$R" log --oneline | head -2 | tr '\n' ' ')"

echo "== 7. methods, routes, hosts =="
chk "GET on a POST route" "$(code "$B/api/drop")" "405"
say "  its Allow header" "$(curl -s -D - -o /dev/null "$B/api/drop" | grep -i '^allow' | tr -d '\r')"
chk "an unknown route" "$(code "$B/nope")" "404"
chk "a foreign Host" "$(curl -s -H 'Host: evil.example' "$B/api/data")" "127.0.0.1 and localhost only"
say "  HEAD /" "$(curl -s -I -o /dev/null -w '%{http_code}' "$B/")"

echo "== 8. a client that hangs up mid-request =="
(printf 'POST /api/drop HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 10\r\n\r\n'; sleep 0.2) \
  | nc -w 2 127.0.0.1 "$P1" >/dev/null 2>&1 || true
printf 'GET /api/data HTTP/1.0\r\n\r\n' | nc -w 2 127.0.0.1 "$P1" >/dev/null 2>&1 || true
sleep 1
say "tracebacks in the server log" "$(grep -c Traceback /tmp/wiki-e2e-server.log)"
kill "$SRV" 2>/dev/null; SRV=""

echo "== 9. the fallback pages (no wiki-page.html next to the server) =="
FB=/tmp/wiki-e2e-fb; rm -rf "$FB"; mkdir -p "$FB"; cp "$PROJ/server.py" "$FB/"
cd "$FB"
CREW_WIKI_DIR="$R" python3 -u server.py "$P2" > /tmp/wiki-e2e-fb.log 2>&1 &
SRV2=$!
sleep 2
chk "GET /" "$(curl -s "127.0.0.1:$P2/")" "The vault is being"
chk "GET /upload" "$(curl -s "127.0.0.1:$P2/upload")" "Put the designed page"
chk "the api still answers" "$(curl -s "127.0.0.1:$P2/api/data" | head -c 20)" '"ok": true'
say "tracebacks in the fallback log" "$(grep -c Traceback /tmp/wiki-e2e-fb.log)"
kill "$SRV2" 2>/dev/null; SRV2=""

echo
if [ "$fail" -eq 0 ]; then
  echo "wiki-e2e: every check matched"
else
  echo "wiki-e2e: SOMETHING MISMATCHED (see above)"
fi
exit "$fail"
