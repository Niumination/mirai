#!/usr/bin/env bash
# Install the habits into every SOUL.md, VERBATIM.
#
# Rules and habits are never saved from memory and never asked of an agent: they
# are written into identity files verbatim with file tools. A small model will
# paraphrase and drop the inconvenient clause.
#
# Idempotent: running it twice does not append twice. Every block is verified by
# grep afterwards, because a claim of installation is not an installation.
#
# Usage: bash install-habits.sh [--check]
set -euo pipefail

HERMES="${HERMES_HOME:-$HOME/.hermes}"
CHECK=0; [ "${1:-}" = "--check" ] && CHECK=1

souls() {
  [ -f "$HERMES/SOUL.md" ] && echo "$HERMES/SOUL.md"
  if [ -d "$HERMES/profiles" ]; then
    for d in "$HERMES"/profiles/*/; do
      [ -f "$d/SOUL.md" ] && [ "$(basename "$d")" != ".deleted" ] && echo "$d/SOUL.md"
    done
  fi
}

BLOCK_WIKI=$(cat <<'EOF'

## The wiki

RECALL: before answering anything the wiki might know - the owner, the business,
things we have read - run `wiki index` (add `wiki index research` when it touches
what we have read), then `wiki search`, then read the pages.
When the wiki does not know, say so in one line and ask one question.
FILE: after real work, file through `wiki file`, `--agent` set to my own profile
name. NEVER create or edit a page under ~/wiki with your own file tools. Never
edit index.md or log.md by hand. Say what you filed - a bare "saved" or "done" is
not a result.
RULES: run `wiki rules` at the start of any session where you will file. The long
form of both habits lives in WIKI.md.
EOF
)

BLOCK_NAME=$(cat <<'EOF'

## Whenever you respond

Whenever you respond to a message, start with the owner's name. You know it.
A scheduled job that must reply exactly [SILENT] still replies exactly [SILENT].
EOF
)

BLOCK_FACT=$(cat <<'EOF'

## Fact vs inference

FACT vs INFERENCE. A recorded fact is a dated thing that happened - an amount
offered, a reply sent, a name, a date. Use freely. An inference is a conclusion
someone drew. File inferences only labelled, with who and when.
NEVER put an inference into anything that goes to a person - email, message,
document. Bring it to me labelled. A claim I cannot trace to a page, I do not act
on, and I say so.
Run `wiki rules` before my first filing in any session.
EOF
)

install_block() {
  local file="$1" marker="$2" block="$3"
  if grep -qF "$marker" "$file"; then
    echo "    already present: $marker"
    return
  fi
  printf '%s\n' "$block" >> "$file"
  echo "    appended: $marker"
}

for soul in $(souls); do
  echo "== $soul"
  if [ "$CHECK" = 1 ]; then
    for m in "own file tools" "owner's name" "FACT vs INFERENCE"; do
      printf '    %-22s %s\n' "$m" "$(grep -c "$m" "$soul" || true)"
    done
    continue
  fi
  cp "$soul" "$soul.bak.$(date +%Y%m%d-%H%M%S)"
  install_block "$soul" "own file tools" "$BLOCK_WIKI"
  install_block "$soul" "owner's name" "$BLOCK_NAME"
  install_block "$soul" "FACT vs INFERENCE" "$BLOCK_FACT"
done

if [ "$CHECK" = 0 ]; then
  echo
  echo "Proof, from the files (a 0 means that profile did not get the block):"
  for soul in $(souls); do
    printf '%s  own-file-tools=%s  name-rule=%s  fact-vs-inference=%s\n' \
      "$soul" "$(grep -c 'own file tools' "$soul")" \
      "$(grep -c "owner's name" "$soul")" "$(grep -c 'FACT vs INFERENCE' "$soul")"
  done
  echo
  echo "Now test each agent from Telegram: ask it \"What do you know about me?\""
  echo "A pass cites a wiki page. A fail says it has no memory — then re-run this script and check the PATH."
fi
