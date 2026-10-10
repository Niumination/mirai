#!/usr/bin/env bash
# offsite-push.sh — the 03:40 job: snapshot, then push the wiki to the private repo.
#
#   bash offsite-push.sh            # what the cron job runs
#   DRY=1 bash offsite-push.sh      # everything except the push
#
# The token rule, restated because it is the whole point of this file:
#   * it lives in ONE file, ~/.config/mirai/wiki-offsite.conf (0600), outside the wiki;
#   * it is read at push time and handed to git through GIT_ASKPASS, so it never
#     appears in argv (ps would show it), never in git's saved remote, never in
#     .git/config, never in a log line, and never in any file inside ~/wiki;
#   * the remote URL is passed on the command line as the non-secret part only.
#
# Exit codes: 0 pushed (or a clean nothing-to-do), 3 the wiki lock was busy,
#             4 no config yet, 5 the push failed. A failure is loud.
set -uo pipefail

CONF="${WIKI_OFFSITE_CONF:-$HOME/.config/mirai/wiki-offsite.conf}"
WIKI="${CREW_WIKI_DIR:-$HOME/wiki}"
HEALTH="$WIKI/_wiki-health.md"
PUSHED=0

say() { printf 'offsite: %s\n' "$*"; }
die() { local code="$1"; shift; printf 'offsite: %s\n' "$*" >&2; exit "$code"; }

heartbeat() {
  [ -d "$WIKI" ] || return 0
  printf 'heartbeat wiki-offsite %s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$1" >> "$HEALTH"
}

[ -d "$WIKI/.git" ] || die 4 "no git repository at $WIKI — run the git step first"
if [ ! -f "$CONF" ]; then
  die 4 "no $CONF yet: run offsite-setup.sh once, paste the token there, and this job takes over"
fi
# shellcheck disable=SC1090
. "$CONF" 2>/dev/null || die 4 "$CONF could not be read"
[ -n "${WIKI_OFFSITE_REPO:-}" ] || die 4 "$CONF has no WIKI_OFFSITE_REPO"

# 1. Snapshot first, through the verb, so what is pushed is committed and the push
#    can never race a write. Exit 3 means another writer holds the lock: nothing is
#    pushed and nothing was snapshotted.
WIKI_CLI="${WIKI_CLI:-$(command -v wiki || true)}"
[ -n "$WIKI_CLI" ] || WIKI_CLI="$(cd "$(dirname "$0")/../skill/wiki" && pwd)/wiki.sh"
if command -v "$WIKI_CLI" >/dev/null 2>&1 || [ -f "$WIKI_CLI" ]; then
  bash "$WIKI_CLI" snapshot --label 'offsite: pre-push' --agent mirai
  rc=$?
  if [ "$rc" = 3 ]; then
    heartbeat "blocked: wiki was busy"
    die 3 "wiki is busy, nothing was pushed"
  elif [ "$rc" != 0 ]; then
    heartbeat "blocked: snapshot failed"
    die 5 "the pre-push snapshot failed (exit $rc) — nothing pushed"
  fi
else
  say "no wiki CLI found; pushing whatever is committed"
fi

# 2. The token, if this remote needs one. A local path or an SSH remote needs none,
#    and that is exactly how this script is tested without a GitHub account.
if [ -n "${WIKI_OFFSITE_TOKEN:-}" ]; then
  ASKPASS="$HOME/.config/mirai/.askpass.sh"
  if [ ! -x "$ASKPASS" ]; then
    mkdir -p "$(dirname "$ASKPASS")"
    {
      printf '#!/bin/sh\n'
      printf '. "%s" 2>/dev/null\n' "$CONF"
      printf 'printf "%%s" "$WIKI_OFFSITE_TOKEN"\n'
    } > "$ASKPASS"
    chmod 700 "$ASKPASS"
  fi
  export GIT_ASKPASS="$ASKPASS"
else
  say "no token in the config: pushing to the remote as it is (fine for ssh or a local path)"
fi
export GIT_TERMINAL_PROMPT=0

if [ "${DRY:-0}" = "1" ]; then
  say "DRY: would push HEAD to $WIKI_OFFSITE_REPO"
  exit 0
fi

BRANCH="$(git -C "$WIKI" symbolic-ref --short HEAD 2>/dev/null || echo main)"
if git -C "$WIKI" -c credential.helper= push --quiet "$WIKI_OFFSITE_REPO" "HEAD:refs/heads/$BRANCH" 2>/tmp/offsite-push.err; then
  PUSHED=1
  HEAD_SHA="$(git -C "$WIKI" rev-parse --short HEAD)"
  say "pushed $BRANCH ($HEAD_SHA) to the private repo"
  heartbeat "ok (pushed $HEAD_SHA)"
else
  REASON="$(tr -d '\n' < /tmp/offsite-push.err | cut -c1-200)"
  rm -f /tmp/offsite-push.err
  heartbeat "blocked: push failed"
  die 5 "the push FAILED: ${REASON:-no detail}"
fi

# 3. The one thing worth checking every night: the token must not have arrived in the
#    repo. Cheap, and it turns a silent leak into a loud line.
if [ -n "${WIKI_OFFSITE_TOKEN:-}" ]; then
  if git -C "$WIKI" grep -qI "$WIKI_OFFSITE_TOKEN" -- . 2>/dev/null; then
    heartbeat "blocked: the token is IN the wiki"
    die 5 "the token appears in a file inside the wiki — remove it and rotate the token now"
  fi
fi
[ "$PUSHED" = 1 ] && say "checked: the token is not in the wiki"
exit 0
