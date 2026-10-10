#!/usr/bin/env bash
# Install MIRAI Mission Control on this Mac, from the folder you unpacked.
#
#   bash install-mac.sh              # install + start
#   bash install-mac.sh --uninstall  # stop + remove the LaunchAgent
#
# What it does: copies nothing you did not ask for, writes the LaunchAgent with
# YOUR home path substituted, loads it, and proves the service answers before it
# says it is done.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
MIRAI_DIR="${MIRAI_DIR:-$HOME/mirai}"
LABEL="com.mirai.mission-control"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST="$PLIST_DIR/$LABEL.plist"
PORT="${MIRAI_PORT:-8800}"

if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "uninstalled. Your data stays in $MIRAI_DIR"
  exit 0
fi

echo "==> 1. Folders"
mkdir -p "$MIRAI_DIR"/{data,docs,proj,data/avatars,data/chat-files,data/docs,data/docs-deleted,data/file-backups,data/archive,lib/mediapipe}
for d in avatars chat-files docs docs-deleted archive file-backups; do
  touch "$MIRAI_DIR/data/$d/.gitkeep"
done
touch "$MIRAI_DIR/data/.gitkeep" "$MIRAI_DIR/.gitkeep"

echo "==> 2. server/ and scripts/ into $MIRAI_DIR"
mkdir -p "$MIRAI_DIR/mission-control"
cp -R "$HERE/server" "$MIRAI_DIR/mission-control/" 2>/dev/null || true
cp -R "$HERE/scripts" "$MIRAI_DIR/mission-control/" 2>/dev/null || true
cp -R "$HERE/launchd" "$MIRAI_DIR/mission-control/" 2>/dev/null || true
# Hand mode's models ship with the package (26+ MB); they are not tracked in git, so a
# clone of the repo will not have them and fetch-mediapipe.sh is the fallback.
SRC_ROOT="$(cd "$HERE/.." && pwd)"
if [ -d "$SRC_ROOT/lib" ]; then
  mkdir -p "$MIRAI_DIR/lib"
  cp -R "$SRC_ROOT/lib/." "$MIRAI_DIR/lib/" 2>/dev/null || true
  n=$(find "$MIRAI_DIR/lib/mediapipe" -type f 2>/dev/null | wc -l | tr -d ' ')
  echo "    Hand mode models in place: $n file(s) under $MIRAI_DIR/lib/mediapipe"
fi

# A zip or a clone can arrive without the executable bit; the printed hints below
# tell the owner to run these directly, so make sure they can.
chmod +x "$MIRAI_DIR"/mission-control/scripts/*.sh 2>/dev/null || true

if [ -f "$HERE/data/roles.json" ]; then
  cp "$HERE/data/roles.json" "$MIRAI_DIR/data/roles.json"
fi
# The dashboard file is yours to drop in; if this bundle carries a starter
# console, place it. The real dashboard is a single ~9 MB HTML file.
if [ -f "$HERE/web/dashboard.html" ] && [ ! -f "$MIRAI_DIR/dashboard.html" ]; then
  cp "$HERE/web/dashboard.html" "$MIRAI_DIR/dashboard.html"
  echo "    starter console placed at $MIRAI_DIR/dashboard.html"
fi

echo "==> 3. Sanity: python3 present?"
/usr/bin/python3 -c 'import sys, zoneinfo; print("    python", sys.version.split()[0])'

echo "==> 4. LaunchAgent"
mkdir -p "$PLIST_DIR"
sed "s|__HOME__|$HOME|g" "$HERE/launchd/$LABEL.plist" > "$PLIST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/$LABEL"

echo "==> 5. Prove it answers"
for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:$PORT/api/ping" >/dev/null 2>&1; then
    echo "    /api/ping: $(curl -s "http://127.0.0.1:$PORT/api/ping")"
    echo "    /api/agents: $(curl -s "http://127.0.0.1:$PORT/api/agents" | head -c 90)..."
    echo
    echo "MIRAI is up:  http://127.0.0.1:$PORT"
    echo "Logs:         $MIRAI_DIR/data/mission-control.log"
    echo "Restart:      $MIRAI_DIR/mission-control/scripts/restart.sh"
    echo "Backup now:   $MIRAI_DIR/mission-control/scripts/backup.sh"
    exit 0
  fi
  sleep 0.5
done

echo "The service did not answer within 20s. Look at:" >&2
echo "  $MIRAI_DIR/data/mission-control.err.log" >&2
exit 1
