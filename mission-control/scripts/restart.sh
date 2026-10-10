#!/usr/bin/env bash
# One way to restart it.
#
# The point of this script is the false green it exists to prevent: one server
# serves both the page and the API, so /api/ping answering proves only that
# SOMETHING is listening. The pid before and after is the proof.
#
# macOS notes (the tutorial this build follows was written for systemd): the
# service is a launchd LaunchAgent, so stopping goes through launchctl, and the
# port owner is found with lsof rather than ss.
set -euo pipefail

PORT="${1:-8800}"
LABEL="com.mirai.mission-control"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
MIRAI_DIR="${MIRAI_DIR:-$HOME/mirai}"
SERVER_DIR="$MIRAI_DIR/mission-control/server"

owner_pid() {
  # lsof is the real answer on macOS (it ships with the system). pgrep is the
  # backstop for any box without it, so this script never reports "none" while a
  # server is plainly answering.
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | head -1 && return
  fi
  pgrep -f "server[.]py $PORT" 2>/dev/null | head -1 || true
}

BEFORE="$(owner_pid)"
echo "port $PORT owner before: ${BEFORE:-none}"

if [ -n "$BEFORE" ]; then
  # Decide HOW to stop it from what it is: a launchd job, or a stray.
  if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
    echo "owner is our LaunchAgent — stopping the job (never kill a unit's pid: it fights KeepAlive)"
    launchctl kickstart -k "gui/$(id -u)/$LABEL"
    for _ in $(seq 1 30); do
      [ -z "$(owner_pid)" ] && break
      sleep 0.2
    done
  else
    echo "owner is a stray process — killing pid $BEFORE"
    kill "$BEFORE" 2>/dev/null || true
    for _ in $(seq 1 30); do
      [ -z "$(owner_pid)" ] && break
      sleep 0.2
    done
  fi
fi

STILL="$(owner_pid)"
if [ -n "$STILL" ]; then
  echo "FAILED: pid $STILL still holds port $PORT" >&2
  exit 1
fi

if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  launchctl kickstart "gui/$(id -u)/$LABEL"
else
  echo "no LaunchAgent installed — starting in the background instead"
  cd "$SERVER_DIR"
  # setsid exists on Linux and not on macOS; nohup is the portable way to outlive
  # this shell. Never let a missing command here read as "the server is broken".
  if command -v setsid >/dev/null 2>&1; then
    setsid nohup python3 server.py "$PORT" >> /tmp/mirai.log 2>&1 &
  else
    nohup python3 server.py "$PORT" >> /tmp/mirai.log 2>&1 &
  fi
fi

AFTER=""
for _ in $(seq 1 50); do
  AFTER="$(owner_pid)"
  [ -n "$AFTER" ] && [ "$AFTER" != "$BEFORE" ] && break
  sleep 0.2
done

if [ -z "$AFTER" ] || [ "$AFTER" = "$BEFORE" ]; then
  echo "FAILED: nothing took port $PORT (see the log)" >&2
  exit 1
fi
echo "new owner: $AFTER (was ${BEFORE:-none})"

# A pid owning the port is not the proof: the page and the API come from the same
# process, so the answer has to come back before this script says it worked.
for _ in $(seq 1 25); do
  if curl -fsS "http://127.0.0.1:$PORT/api/ping" 2>/dev/null; then
    echo
    exit 0
  fi
  sleep 0.2
done

echo "FAILED: pid $AFTER owns port $PORT but the API is not answering (see the log)" >&2
exit 1

echo "FAILED: nothing took port $PORT (see the log)" >&2
exit 1
