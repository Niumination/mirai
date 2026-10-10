#!/usr/bin/env bash
# link.sh — the one-tap link, for the phone.
#
#   bash link.sh              # prints the https link on the tailnet, and the local one
#   bash link.sh --local      # only 127.0.0.1
#
# The gate accepts the token as ?k=<token> and sets a thirty-day cookie when it
# arrives that way, so this link is a single tap from a phone and stays signed in.
# The token is NOT single use and is not rotated by using it.
#
# Three things this script refuses to do, because each one would undo the gate:
#   * it never prints the token to a shell history or a file — only to your terminal;
#   * it never switches the gate on by itself (MIRAI_AUTH=on is your decision);
#   * it never suggests `tailscale funnel`, which would put this on the public internet
#     instead of your tailnet.
set -uo pipefail

MIRAI_DIR="${MIRAI_DIR:-$HOME/mirai}"
DATA_DIR="${MIRAI_DATA_DIR:-$MIRAI_DIR/data}"
PORT="${MIRAI_PORT:-8800}"
TOKEN_FILE="$DATA_DIR/auth.token"
AUTH="${MIRAI_AUTH:-}"
LOCAL_ONLY=0
[ "${1:-}" = "--local" ] && LOCAL_ONLY=1

say() { printf '%s\n' "$*"; }
die() { printf 'link: %s\n' "$*" >&2; exit 1; }

# The gate has to be on, or the link is just a URL with a pointless tail on it.
if [ "$AUTH" != "on" ] && [ "$AUTH" != "1" ] && [ "$AUTH" != "true" ]; then
  say "the gate is OFF (MIRAI_AUTH is not on), so no token is needed and there is no link to print."
  say "Turn it on first:  launchctl setenv MIRAI_AUTH on   then   bash ~/mirai/mission-control/scripts/restart.sh"
fi

[ -f "$TOKEN_FILE" ] || die "no token yet at $TOKEN_FILE. The gate writes it on its first start; run restart.sh once."
TOKEN="$(tr -d '\n' < "$TOKEN_FILE")"
[ -n "$TOKEN" ] || die "$TOKEN_FILE is empty"

# Where are we reachable from? Tailscale first, and its userspace socket matters: when
# tailscaled runs in userspace mode the binary needs --socket and a plain `tailscale
# status` fails with "cannot connect to the tailscaled".
TS="$(command -v tailscale || true)"
TS_SOCKET=""
for cand in "/var/run/tailscaled.socket" "$HOME/.tailscale/tailscaled.socket" "/tmp/tailscaled.socket"; do
  [ -S "$cand" ] && TS_SOCKET="$cand" && break
done
TLS_PORT="${MIRAI_TLS_PORT:-}"          # set this if `tailscale serve` is on a port other than 443

tailnet_name() {
  [ -n "$TS" ] || return 1
  local out
  if [ -n "$TS_SOCKET" ]; then
    out="$("$TS" --socket "$TS_SOCKET" status --json 2>/dev/null)" || out="$("$TS" status --json 2>/dev/null)" || return 1
  else
    out="$("$TS" status --json 2>/dev/null)" || return 1
  fi
  printf '%s' "$out" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
name = (d.get("Self") or {}).get("DNSName") or ""
print(name.rstrip("."))
' 2>/dev/null
}

LOCAL="http://127.0.0.1:$PORT/?k=$TOKEN"
say "$LOCAL"
if [ "$LOCAL_ONLY" = 1 ]; then
  exit 0
fi

NAME="$(tailnet_name || true)"
if [ -n "$NAME" ]; then
  if [ -n "$TLS_PORT" ] && [ "$TLS_PORT" != "443" ]; then
    say "https://$NAME:$TLS_PORT/?k=$TOKEN"
  else
    say "https://$NAME/?k=$TOKEN"
  fi
  # The Host header the proxy sends is the tailnet name: without it the server answers
  # 403 to its own proxy, which is a confusing five minutes. Print the exact line.
  say ""
  say "if the https link answers 403, the server's host allowlist does not know this name yet:"
  say "  launchctl setenv MIRAI_HOSTS \"$NAME\" && bash ~/mirai/mission-control/scripts/restart.sh"
else
  say ""
  say "no tailnet name found (tailscale not installed, or tailscaled is not reachable)."
  say "the local link above works on this machine; for the phone, run the tailscale step first:"
  say "  bash $(cd "$(dirname "$0")" && pwd)/tailscale-serve.sh"
fi
