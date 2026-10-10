#!/usr/bin/env bash
# Create the specialists as persistent Hermes profiles — on the Mac, from here.
#
# What this does, and the order it does it in, is the whole point:
#   1. hermes profile create <profile> --clone
#   2. copy across whichever of auth.json, config.yaml and .env the default
#      profile has and the new one lacks. A new profile does NOT get the login,
#      so it cannot answer a single turn, and nothing done in chat fixes it.
#      --clone copies config.yaml, .env, SOUL.md and skills but never auth.json,
#      and a bare create gives a stub .env with no credentials in it. JUDGE BY
#      WHAT IS ON DISK, not by the flag you used.
#      .env is copied WITHOUT the platform tokens (TELEGRAM_*, DISCORD_*, …):
#      a second profile holding the owner's Telegram token makes the gateway
#      refuse the duplicate on every start.
#   3. write SOUL.md — us, not an agent. A small model will paraphrase a long
#      instruction and quietly drop the clause it finds inconvenient.
#   4. verify with a real turn. A profile without a login answers nothing.
#
# Usage:  bash create-fleet.sh [--dry-run]
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
HERMES="${HERMES_HOME:-$HOME/.hermes}"
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1

HERMES_BIN="$(command -v hermes || true)"
for c in /opt/homebrew/bin/hermes /usr/local/bin/hermes "$HOME/.local/bin/hermes"; do
  [ -n "$HERMES_BIN" ] && break
  [ -x "$c" ] && HERMES_BIN="$c"
done
[ -n "$HERMES_BIN" ] || { echo "hermes CLI not found. Find it, then re-run." >&2; exit 1; }
echo "hermes: $HERMES_BIN"

copy_credentials() {
  local profile="$1" src="$HERMES" dst="$HERMES/profiles/$profile"
  for f in auth.json config.yaml .env; do
    [ -e "$src/$f" ] || continue
    [ -e "$dst/$f" ] && continue
    if [ "$f" = ".env" ]; then
      # strip the platform tokens: a duplicate bot token breaks the gateway
      grep -vE '^(TELEGRAM|DISCORD|SLACK|WHATSAPP|MATRIX)_' "$src/.env" > "$dst/.env" || true
      chmod 600 "$dst/.env"
      echo "    copied .env (platform tokens removed)"
    else
      cp -p "$src/$f" "$dst/$f"      # -p keeps 0600; a plain cp would leave 0644
      echo "    copied $f"
    fi
  done
}

for spec in "research:RESEARCH-SOUL.md" "writer:CONTENT-WRITER-SOUL.md" "developer:DEVELOPER-SOUL.md"; do
  profile="${spec%%:*}"
  soul_file="$HERE/profiles/${spec##*:}"
  target="$HERMES/profiles/$profile"

  echo "== $profile"
  if [ -d "$target" ] && [ -f "$target/SOUL.md" ]; then
    echo "    already exists — leaving the profile alone, refreshing its SOUL"
  elif [ "$DRY" = 1 ]; then
    echo "    would run: hermes profile create $profile --clone"
  else
    "$HERMES_BIN" profile create "$profile" --clone
  fi

  if [ "$DRY" = 0 ]; then
    copy_credentials "$profile"
    cp "$soul_file" "$target/SOUL.md"
    echo "    SOUL.md written from ${spec##*:}"
    printf '    verifying with one real turn… '
    reply="$("$HERMES_BIN" -p "$profile" chat -q "Who are you?" -Q --source mirai -c mirai-probe --create-if-missing 2>&1 | tail -3 | tr '\n' ' ')"
    case "$reply" in
      *""|"") echo "EMPTY — this profile has no working login. Fix before using it." ;;
      *) echo "ok: ${reply:0:90}" ;;
    esac
  fi
done

echo
echo "Next:"
echo "  1. bash scripts/install-habits.sh   # the wiki habits, verbatim, into every SOUL"
echo "  2. set the display name:  curl -s -X POST localhost:8800/api/settings -d '{\"settings\":{\"display_name\":\"<you>\"}}'"
echo "  3. the Telegram topics and the routing plugin: see config/telegram-routing.md"
