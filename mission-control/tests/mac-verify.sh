#!/usr/bin/env bash
# mac-verify.sh — the things only this Mac can prove.
#
#   bash mac-verify.sh              # ~10 seconds, read-only, no model calls
#   bash mac-verify.sh --turn       # also does ONE real Hermes turn (costs a model call)
#   HOME=/tmp/x bash mac-verify.sh  # pointless on a Mac: the point is THIS machine
#
# WHY THIS FILE EXISTS
#   Everything in docs/STATUS-UJI.md that says "must be proven on the Mac" lives here as
#   a check, so proving it is one command instead of a page of instructions. Every check
#   is READ-ONLY: it starts nothing, stops nothing, and never edits ~/.hermes. The one
#   exception is --turn, which asks an agent one question, and says so before it does.
#
#   A failing check prints the exact command that fixes or explains it. Nothing here
#   "should work": each line either saw it work or says it did not.
set -uo pipefail

MIRAI_DIR="${MIRAI_DIR:-$HOME/mirai}"
DATA_DIR="${MIRAI_DATA_DIR:-$MIRAI_DIR/data}"
HERMES="${HERMES_HOME:-$HOME/.hermes}"
PORT="${MIRAI_PORT:-8800}"
LABEL="com.mirai.mission-control"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
WIKI="${CREW_WIKI_DIR:-$HOME/Desktop/Niumination/wiki}"
DO_TURN=0
[ "${1:-}" = "--turn" ] && DO_TURN=1

PASS=0; FAIL=0; SKIP=0
ok()   { printf '  \033[32mPASS\033[0m  %-44s %s\n' "$1" "${2:-}"; PASS=$((PASS+1)); }
bad()  { printf '  \033[31mFAIL\033[0m  %-44s %s\n' "$1" "${2:-}"; FAIL=$((FAIL+1)); }
skip() { printf '  \033[33mSKIP\033[0m  %-44s %s\n' "$1" "${2:-}"; SKIP=$((SKIP+1)); }
head_() { printf '\n== %s\n' "$1"; }
has()  { command -v "$1" >/dev/null 2>&1; }

json() { python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(9)
try: print(eval('d'+sys.argv[1]))
except Exception: print('')" "$2" 2>/dev/null; }

echo "MIRAI on this Mac — $(date '+%Y-%m-%d %H:%M')  (HOME=$HOME, port=$PORT)"

# ---------------------------------------------------------------- launchd
head_ "launchd (the service comes back by itself)"
if [ -f "$PLIST" ]; then
  ok "LaunchAgent plist exists" "$PLIST"
  if has plutil && plutil -lint "$PLIST" >/dev/null 2>&1; then
    ok "plist is valid XML" "plutil -lint"
  elif has plutil; then
    bad "plist is NOT valid XML" "plutil -lint $PLIST"
  fi
else
  bad "no LaunchAgent at $PLIST" "bash $MIRAI_DIR/mission-control/scripts/install-mac.sh"
fi
if has launchctl; then
  OUT="$(launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null)"
  if [ -n "$OUT" ]; then
    ok "job is loaded in launchd" "$(printf '%s' "$OUT" | awk '/state =/{print $3; exit}')"
    printf '%s' "$OUT" | grep -qE "keepalive( = 1| \\||$)" \
      && ok "KeepAlive is on (it restarts itself)" || bad "KeepAlive is OFF" "check the plist"
  else
    bad "job is not loaded" "launchctl bootstrap gui/$(id -u) $PLIST"
  fi
fi

# ---------------------------------------------------------------- the port, and only loopback
head_ "the port, and nowhere else"
if has lsof; then
  LISTEN="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null)"
  if [ -n "$LISTEN" ]; then
    ok "something owns $PORT" "$(printf '%s' "$LISTEN" | awk 'NR==1{print $1" pid "$2}')"
    if printf '%s' "$LISTEN" | awk 'NR>1{print $9}' | grep -qv "127.0.0.1:"; then
      bad "it listens on a NON-loopback address" "$(printf '%s' "$LISTEN" | awk 'NR>1{print $9}')"
    else
      ok "bound to 127.0.0.1 only" "no public listener"
    fi
  else
    bad "nothing is listening on $PORT" "bash $MIRAI_DIR/mission-control/scripts/restart.sh"
  fi
  if lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -v "127.0.0.1\|\[::1\]" | grep -q ":$PORT "; then
    bad "a public interface answers on $PORT" "stop and investigate before continuing"
  else
    ok "no public interface on $PORT" "reachable by loopback and the tailnet proxy only"
  fi
else
  skip "lsof missing" "it ships with macOS, so this is unusual"
fi

# ---------------------------------------------------------------- the API answers
head_ "the API answers, on this machine's real numbers"
PING="$(curl -s -m 5 "http://127.0.0.1:$PORT/api/ping")"
case "$PING" in *'"ok": true'*) ok "GET /api/ping" "$PING";; *) bad "GET /api/ping" "$PING";; esac

AGENTS="$(curl -s -m 15 "http://127.0.0.1:$PORT/api/agents")"
N="$(printf '%s' "$AGENTS" | json '' "['agents'].__len__()")"
case "$N" in
  ''|0) bad "no agents found in ~/.hermes" "the fleet is empty or $HERMES is not where the server looks";;
  *)    ok "agents found: $N" "$(printf '%s' "$AGENTS" | json '' "['fleet']['seats']") seats";;
esac

HEALTH="$(curl -s -m 15 "http://127.0.0.1:$PORT/api/health")"
OSNAME="$(printf '%s' "$HEALTH" | json '' "['host']['os']")"
MEM="$(printf '%s' "$HEALTH" | json '' "['memory']['pct']")"
DIAG="$(printf '%s' "$HEALTH" | json '' "['diagnostics']['status']")"
CHECKS="$(printf '%s' "$HEALTH" | json '' "['diagnostics']['passed']")"
if [ -n "$OSNAME" ]; then
  case "$OSNAME" in
    *macOS*|*Darwin*) ok "health reads this Mac" "$OSNAME, memory ${MEM}% used";;
    *) bad "health reports '$OSNAME'" "expected macOS/Darwin: the sampler fell back to the Linux path";;
  esac
  ok "diagnostics ran" "$CHECKS check(s) passed, status: $DIAG"
else
  bad "GET /api/health returned nothing usable" "bash $MIRAI_DIR/mission-control/tests/smoke.sh"
fi

# ---------------------------------------------------------------- Hermes itself
head_ "Hermes (does not write to ~/.hermes)"
if has hermes; then
  ok "hermes is on PATH" "$(command -v hermes)"
  if hermes profile list >/dev/null 2>&1; then
    ok "hermes profile list works" "$(hermes profile list 2>/dev/null | wc -l | tr -d ' ') line(s)"
  else
    bad "hermes answered with an error" "run: hermes profile list"
  fi
  if hermes cron list >/dev/null 2>&1; then
    JOBS="$(hermes cron list 2>/dev/null)"
    MISSING=""
    for j in wiki-dropbox wiki-librarian wiki-lint wiki-opening-snapshot wiki-closing-snapshot; do
      printf '%s' "$JOBS" | grep -q "$j" || MISSING="$MISSING $j"
    done
    if [ -z "$MISSING" ]; then
      ok "five wiki jobs (adopsi: tanpa mail-sweep/offsite)" "hermes cron list"
    else
      bad "missing cron jobs:$MISSING" "create them from memory/schedule/cron-jobs.json"
    fi
    EXTRA=""
    for j in wiki-mail-sweep wiki-offsite; do
      printf '%s' "$JOBS" | grep -q "$j" && EXTRA="$EXTRA $j"
    done
    if [ -n "$EXTRA" ]; then
      skip "mail-sweep/offsite present (not required)" "$EXTRA"
    else
      ok "mail-sweep and offsite not scheduled" "sesuai ADOPT-MAC"
    fi
  else
    skip "hermes cron list did not answer" "may need a gateway restart"
  fi
else
  bad "hermes is not on PATH" "the dashboard can find agents but cannot talk to one"
fi

# ---------------------------------------------------------------- the wiki and its safety net
head_ "the wiki, its verbs, and its git safety net"
if has wiki; then
  ok "wiki is on PATH" "$(command -v wiki)"
  if [ -d "$WIKI/.git" ]; then
    ok "the wiki is a git repository" "$(git -C "$WIKI" rev-list --count HEAD 2>/dev/null) commit(s)"
    if git -C "$WIKI" config --local user.name >/dev/null 2>&1; then
      ok "identity is repo-local" "$(git -C "$WIKI" config --local user.name)"
    else
      bad "no repo-local git identity" "git -C $WIKI config user.name MIRAI"
    fi
    LAST="$(git -C "$WIKI" log -1 --format=%cr 2>/dev/null)"
    ok "last commit" "${LAST:-none yet}"
  else
    bad "the wiki is not under git yet" "DEPLOY-MAC, langkah 3d"
  fi
  if wiki snapshot --help >/dev/null 2>&1 || wiki help 2>&1 | grep -q snapshot; then
    ok "the snapshot verb exists" "the nightly jobs and the dashboard button use it"
  else
    bad "this wiki CLI has no snapshot verb" "reinstall ~/.local/bin/wiki from the package"
  fi
else
  bad "wiki is not on PATH" "DEPLOY-MAC, langkah 2"
fi

# ---------------------------------------------------------------- dashboard + hand mode files
head_ "the console and Hand mode's files"
PAGE_CODE="$(curl -s -o /tmp/macverify-page.html -w '%{http_code}' -m 15 "http://127.0.0.1:$PORT/")"
if [ -f /tmp/macverify-page.html ]; then
  SIZE="$(wc -c < /tmp/macverify-page.html | tr -d ' ')"
else
  SIZE=0
fi
case "$PAGE_CODE" in
  200) ok "GET / serves a page" "$SIZE bytes";;
  *)   bad "GET / answered $PAGE_CODE" "put the dashboard at $MIRAI_DIR/dashboard.html";;
esac
LIB="$(curl -s -o /dev/null -w '%{http_code}' -m 20 "http://127.0.0.1:$PORT/lib/mediapipe/hand_landmarker.task")"
case "$LIB" in
  200) ok "Hand mode's model is served" "/lib/mediapipe/hand_landmarker.task";;
  *)   bad "Hand mode's model is $LIB" "bash $MIRAI_DIR/mission-control/scripts/fetch-mediapipe.sh";;
esac
if [ -f "$DATA_DIR/auth.token" ]; then
  ok "gate token exists" "$(ls -l "$DATA_DIR/auth.token" | awk '{print $1}')"
fi
if [ -f "$MIRAI_DIR/mission-control/secrets.env" ]; then
  M="$(ls -l "$MIRAI_DIR/mission-control/secrets.env" | awk '{print $1}')"
  case "$M" in -rw-------) ok "secrets.env is 0600";; *) bad "secrets.env is $M" "chmod 600";; esac
fi

# ---------------------------------------------------------------- backups
head_ "backups (keep a copy)"
BACKUP_ROOT="$(dirname "$MIRAI_DIR")/$(basename "$MIRAI_DIR")-backups"
NEWEST="$(ls -1dt "$BACKUP_ROOT"/*/ 2>/dev/null | head -1)"
if [ -n "$NEWEST" ]; then
  AGE_H=$(( ( $(date +%s) - $(stat -f %m "$NEWEST" 2>/dev/null || echo 0) ) / 3600 ))
  if [ "$AGE_H" -lt 36 ]; then
    ok "a snapshot from the last day and a half" "$(basename "$NEWEST") (${AGE_H}h old)"
  else
    bad "newest snapshot is ${AGE_H}h old" "bash $MIRAI_DIR/mission-control/scripts/backup.sh, and check the launchd job"
  fi
else
  skip "no snapshots yet" "bash $MIRAI_DIR/mission-control/scripts/backup.sh"
fi

# ---------------------------------------------------------------- one real turn (opt in)
head_ "one real turn (the only check that costs anything)"
if [ "$DO_TURN" = 1 ]; then
  CODE="$(printf '%s' "$AGENTS" | json '' "['agents'][0]['code']")"
  if [ -z "$CODE" ]; then
    bad "no agent to ask" "run without --turn and fix the agents check first"
  else
    echo "  asking $CODE to reply with one word…"
    REPLY="$(curl -s -m 120 -X POST "http://127.0.0.1:$PORT/api/chat" \
             -H 'Content-Type: application/json' \
             --data-binary "{\"agent\":\"$CODE\",\"message\":\"Reply with the single word: pong\"}")"
    case "$REPLY" in
      *'"ok": true'*) ok "a real turn came back" "$(printf '%s' "$REPLY" | head -c 120)";;
      *) bad "the turn failed" "$(printf '%s' "$REPLY" | head -c 200)";;
    esac
  fi
else
  skip "not attempted" "re-run with --turn when you want to prove a live model call"
fi

# ---------------------------------------------------------------- voice, if it is on
head_ "voice (only if you use it)"
VC="$(curl -s -m 10 "http://127.0.0.1:$PORT/api/voice/config")"
if printf '%s' "$VC" | grep -q '"ok": true'; then
  UP="$(printf '%s' "$VC" | json '' "['config']['engine_up']")"
  if [ "$UP" = "True" ]; then ok "the local voice engine is up" "127.0.0.1:8768"
  else skip "the local voice engine is not running" "start it, or leave voice on mode 2/3"; fi
fi

printf '\n== %s passed, %s failed, %s skipped\n' "$PASS" "$FAIL" "$SKIP"
if [ "$FAIL" -eq 0 ]; then
  echo "Everything this Mac can prove, it just proved."
  exit 0
fi
echo "Fix the FAIL lines above, then run this again. The SKIP lines are not failures."
exit 1
