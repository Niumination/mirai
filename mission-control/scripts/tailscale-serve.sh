#!/usr/bin/env bash
# tailscale-serve.sh — the dashboard on your tailnet, and nowhere else.
#
#   bash tailscale-serve.sh                 # HTTPS on 443 of the tailnet name
#   bash tailscale-serve.sh 8443            # a port of your choosing
#   bash tailscale-serve.sh --status        # what is mapped right now, change nothing
#   bash tailscale-serve.sh --remove        # undo the mapping
#
# Why this script exists rather than a line in a document: `tailscale serve` config is
# MACHINE WIDE. A serve command with no port takes 443 and silently replaces whatever
# was there, so the safe order is read-first, name-the-port-always, then one mapping.
#
# WHAT THIS NEVER DOES: `tailscale funnel`. Funnel publishes to the public internet.
# Serve publishes to your tailnet, which is the whole point.
set -uo pipefail

PORT="${1:-443}"
[ "${1:-}" = "--status" ] && PORT=""
ACTION="serve"
[ "${1:-}" = "--remove" ] && ACTION="remove" && PORT="443"

MIRAI_PORT="${MIRAI_PORT:-8800}"
MIRAI_DIR="${MIRAI_DIR:-$HOME/mirai}"
say() { printf '%s\n' "$*"; }
die() { printf 'tailscale: %s\n' "$*" >&2; exit 1; }

# --- 1. tailscale present, and reachable in either mode ------------------------------
TS="$(command -v tailscale || true)"
[ -n "$TS" ] || [ -x /Applications/Tailscale.app/Contents/MacOS/Tailscale ] \
  && TS="${TS:-/Applications/Tailscale.app/Contents/MacOS/Tailscale}"
[ -n "$TS" ] || die "tailscale is not installed. Install it from https://tailscale.com/download/mac and run this again."

# Userspace mode has no /var/run socket: every call then needs --socket, and without it
# `tailscale status` says "cannot connect to the tailscaled" while everything is fine.
SOCKET=""
for cand in "/var/run/tailscaled.socket" "$HOME/.tailscale/tailscaled.socket" "/tmp/tailscaled.socket"; do
  [ -S "$cand" ] && SOCKET="$cand" && break
done
ts() {
  if [ -n "$SOCKET" ]; then "$TS" --socket "$SOCKET" "$@" 2>/dev/null || "$TS" "$@" 2>/dev/null
  else "$TS" "$@" 2>/dev/null; fi
}

NAME="$(ts status --json | python3 -c '
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(1)
print(((d.get("Self") or {}).get("DNSName") or "").rstrip("."))
')"
[ -n "$NAME" ] || die "tailscale is installed but not up (no tailnet name). Run: tailscale up"
say "tailnet name: $NAME"

# --- 2. read the current mapping BEFORE touching it ---------------------------------
say ""
say "== serve config as it is right now =="
ts serve status || true

if [ "$ACTION" = "remove" ]; then
  ts serve --https="$PORT" off || die "could not remove the mapping (it may not exist)"
  say "removed. The server itself is untouched and still on 127.0.0.1:$MIRAI_PORT."
  exit 0
fi
[ -z "$PORT" ] && exit 0

# --- 3. the one mapping, port named, backgrounded ------------------------------------
say ""
say "==> mapping https://$NAME:$PORT/  ->  http://127.0.0.1:$MIRAI_PORT"
if [ "$PORT" = "443" ]; then
  ts serve --bg --https=443 "http://127.0.0.1:$MIRAI_PORT" || die "serve failed"
else
  ts serve --bg --https="$PORT" "http://127.0.0.1:$MIRAI_PORT" || die "serve failed"
fi

say ""
say "== serve config after =="
ts serve status

# --- 4. the server must accept the proxy's Host header -------------------------------
# The bind stays 127.0.0.1: Tailscale is a proxy, not a second listener. But the proxy
# asks as the tailnet name, so the allowlist has to know it, or every request is a 403.
if [ -w "$MIRAI_DIR" ] || [ -d "$MIRAI_DIR" ]; then
  say ""
  say "the server's host allowlist needs this name (one line, then a restart):"
  say "  launchctl setenv MIRAI_HOSTS \"$NAME\""
  say "  bash $MIRAI_DIR/mission-control/scripts/restart.sh"
fi

# --- 5. prove it is not on the internet ---------------------------------------------
say ""
say "==> nothing on a public interface? (a line here means STOP and tell me)"
if command -v lsof >/dev/null 2>&1; then
  lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -v "127.0.0.1\|\[::1\]" | grep -E ":$MIRAI_PORT|:443|:$PORT" || \
    say "    clean: the only listener for these ports is on 127.0.0.1"
else
  say "    (lsof not found: check by hand that nothing listens on $MIRAI_PORT off loopback)"
fi

URL="https://$NAME:$PORT/"
[ "$PORT" = "443" ] && URL="https://$NAME/"
say ""
say "open it on your phone:  $URL        (add ?k=<token> once if the gate is on: bash link.sh)"
cat <<'EOF'

If you ever run `tailscale funnel` instead, three things change:
  1. the dashboard becomes reachable by ANYONE on the internet, not just your devices;
  2. the only thing standing between them and your crew is a token in a URL;
  3. this machine starts answering to strangers, and every line it serves is a log entry.
Serve is enough for a phone on your own tailnet. Funnel is not installed by this build.
EOF
