#!/usr/bin/env bash
# offsite-setup.sh — the one command that takes the token invisibly.
#
# From the pack: "Give me one terminal command that asks for the token invisibly and
# stores it in a file outside the wiki, readable only by me. I paste the token into
# the terminal, never here — a token in this chat is a token in the transcript."
#
#   bash offsite-setup.sh
#
# What it does:
#   1. asks for your private repo URL and the fine-grained token, without echoing either;
#   2. writes them to ~/.config/mirai/wiki-offsite.conf, mode 0600, outside ~/wiki;
#   3. proves the token works with a real read against the repo (git ls-remote), so a
#      wrong token is caught now and not at 03:40 in the morning;
#   4. prints what to check, and never prints or logs the token itself.
#
# To change or remove it: run this script again, or  rm ~/.config/mirai/wiki-offsite.conf
set -euo pipefail

CONF_DIR="$HOME/.config/mirai"
CONF="$CONF_DIR/wiki-offsite.conf"
WIKI="${CREW_WIKI_DIR:-$HOME/wiki}"

die() { printf 'offsite-setup: %s\n' "$*" >&2; exit 1; }

[ -d "$WIKI/.git" ] || die "the wiki at $WIKI is not a git repository yet — do the git step first (DEPLOY-MAC, langkah 3d)"

echo "Private repo URL, e.g. https://github.com/<you>/<repo>.git"
printf 'repo URL: '
read -r REPO_URL
[ -n "$REPO_URL" ] || die "no URL, nothing written"

echo
echo "The fine-grained token (Contents: read and write on that one repo)."
echo "It is not echoed, not stored in your shell history, and never leaves this machine."
printf 'token (hidden): '
read -rs TOKEN
echo
[ -n "$TOKEN" ] || die "no token, nothing written"

mkdir -p "$CONF_DIR"
chmod 700 "$CONF_DIR"
umask 077
TMP="$CONF.tmp.$$"
{
  printf '# MIRAI wiki offsite copy. Contains a secret: keep it 0600.\n'
  printf '# Written by offsite-setup.sh on %s\n' "$(date '+%Y-%m-%d %H:%M')"
  printf 'WIKI_OFFSITE_REPO=%s\n' "$REPO_URL"
  printf 'WIKI_OFFSITE_TOKEN=%s\n' "$TOKEN"
} > "$TMP"
chmod 600 "$TMP"
mv "$TMP" "$CONF"

echo
echo "==> proving the token can read the repo (no push yet)"
ASKPASS="$CONF_DIR/.askpass.sh"
{
  printf '#!/bin/sh\n'
  printf '# the token, straight from the config, for git to read once\n'
  printf '. "%s" 2>/dev/null\n' "$CONF"
  printf 'printf "%%s" "$WIKI_OFFSITE_TOKEN"\n'
} > "$ASKPASS"
chmod 700 "$ASKPASS"

if GIT_ASKPASS="$ASKPASS" GIT_TERMINAL_PROMPT=0 \
   git -c credential.helper= ls-remote --heads "$REPO_URL" >/dev/null 2>&1; then
  echo "    OK: the repo answered. The token works."
else
  echo "    FAILED: the repo did not answer. Common causes, in this order:" >&2
  echo "      1. the token has no Contents: read permission on THIS repo;" >&2
  echo "      2. the URL is wrong (it must end in .git);" >&2
  echo "      3. the repo does not exist yet." >&2
  echo "    Nothing was pushed. Fix it and run this script again." >&2
  exit 1
fi

cat <<EOF

Done. Three things to check, in order:
  1. the file is yours alone:   ls -l $CONF        (expect -rw-------)
  2. nothing in the wiki holds the token:
       grep -ri "\$(sed -n 's/^WIKI_OFFSITE_TOKEN=//p' $CONF | cut -c1-8)" $WIKI && echo "LEAK" || echo "clean"
  3. the first push, by hand, now that you are watching:
       bash $(cd "$(dirname "$0")" && pwd)/offsite-push.sh
     Expect: "snapshot" then "pushed". Every later push is the 03:40 cron job.
EOF
