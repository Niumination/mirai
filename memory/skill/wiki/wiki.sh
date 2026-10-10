#!/usr/bin/env bash
# wiki — the one way every agent reaches the crew wiki.
#
# Nine verbs. Four read and never lock: index, search, read, rules.
# Five write and always lock: file, reindex, log, delete, snapshot.
#
# Git is the safety net and it is not optional: every mutating verb commits its own
# write, inside the lock it already holds, staging only the paths it touched, with
# the message "<agent>: <page-name>". A failed commit is loud, because a page that
# is on disk but not in history is a page that is not recoverable - which is the
# only reason the commit exists at all.
#
# The guarantees matter more than the code:
#   * file replaces a page from stdin and writes the page, its index line and
#     its log line as ONE operation.
#   * It refuses rather than guesses: a name that exists in another folder, an
#     existing page given no hash, a hash that no longer matches, a raw/ slug
#     that exists.
#   * delete quarantines to an underscore folder; nothing is ever destroyed,
#     and raw/ is never removed at all.
#   * log refuses page names that were never filed, so an agent cannot log a
#     filing it never did.
#
# Install as `wiki` on every profile's PATH. Root is WIKI_DIR, taken from
# CREW_WIKI_DIR when set (a container keeps each profile's home separate, so the
# wiki's real path is pinned once and used everywhere).
# Niumination: wiki lives in the ecosystem root, not $HOME/wiki (moved 10 Okt 2026).
set -euo pipefail

WIKI="${CREW_WIKI_DIR:-$HOME/Desktop/Niumination/wiki}"
PROCESSED="$WIKI/processed"
RAW="$WIKI/raw"
INDEX="$WIKI/index.md"
LOG="$WIKI/log.md"
RULES="$WIKI/WIKI.md"
LOCK="$WIKI/.wiki.lock"
LOCK_WAIT="${WIKI_LOCK_WAIT:-30}"

die() { printf 'wiki: %s\n' "$*" >&2; exit 1; }

# Safe characters only in names: nothing here can forge a log line.
check_name() {
  case "$1" in
    *[!a-z0-9-]*) die "page names are lowercase-with-dashes: '$1'" ;;
    ""|-*|*-)     die "bad page name: '$1'" ;;
  esac
}

check_agent() {
  case "$1" in
    *[!A-Za-z0-9_-]*) die "bad agent name: '$1'" ;;
  esac
}

# macOS has no flock; mkdir is atomic on both platforms and is used as the lock
# itself. The negative LOCK_WAIT semantics (0 = non-blocking) are preserved.
lock() {
  mkdir -p "$WIKI"
  mkdir "$LOCK" 2>/dev/null || {
    # Stale lock older than 5 minutes is broken: a killed process leaves no trap.
    find "$LOCK" -maxdepth 0 -mmin +5 -delete 2>/dev/null
    mkdir "$LOCK" 2>/dev/null || die "wiki is busy, try again"
  }
  trap 'rmdir "$LOCK" 2>/dev/null' EXIT INT TERM
}

# The snapshot verb is called by the nightly jobs and by the dashboard's button, so
# "the wiki is busy" has to be machine-readable: exit 3, with the sentence the
# dashboard shows and the pack asks for word for word.
lock_for_snapshot() {
  mkdir -p "$WIKI"
  mkdir "$LOCK" 2>/dev/null || {
    find "$LOCK" -maxdepth 0 -mmin +5 -delete 2>/dev/null
    if ! mkdir "$LOCK" 2>/dev/null; then
      printf 'wiki: wiki is busy, nothing was snapshotted\n' >&2
      exit 3
    fi
  }
  trap 'rmdir "$LOCK" 2>/dev/null' EXIT INT TERM
}

# ---------------------------------------------------------------------------
# git: inside the lock, only what this verb touched
# ---------------------------------------------------------------------------
git_ready() { [ -d "$WIKI/.git" ] && command -v git >/dev/null 2>&1; }

commit_paths() {            # commit_paths "<agent>: <page>" <path> [<path>...]
  local msg="$1"; shift
  git_ready || return 0                      # no repo yet: nothing to be safe with
  git -C "$WIKI" add -- "$@" >/dev/null 2>&1 || die "git add failed for: $*"
  git -C "$WIKI" diff --cached --quiet && return 0     # nothing changed: no empty commit
  # The identity is set repo-locally at setup; -c is the belt to that pair of braces,
  # and it deliberately is NOT --global: the owner's other repositories are not ours.
  if ! git -C "$WIKI" -c user.name=MIRAI -c user.email=mirai@localhost \
        commit -q -m "$msg"; then
    die "COMMIT FAILED. $msg is written to disk but not in history — fix git and file it again (this is the one failure that must never pass quietly)"
  fi
}

today() { date +%Y-%m-%d; }

path_of() {  # echo the page path if it exists anywhere, else empty
  local name="$1" p
  for p in "$PROCESSED"/personal/"$name".md "$PROCESSED"/business/"$name".md \
           "$PROCESSED"/research/"$name".md "$PROCESSED"/research/concepts/"$name".md; do
    [ -f "$p" ] && { printf '%s' "$p"; return 0; }
  done
  printf ''
}

hash_of() { shasum -a 256 "$1" 2>/dev/null | cut -d' ' -f1 || sha256sum "$1" | cut -d' ' -f1; }

index_line_for() {  # name, folder, summary, aka
  local extra=""
  [ -n "${4:-}" ] && extra=" (aka $4)"
  printf -- '- [[%s]] — %s%s' "$1" "$3" "$extra"
}

# --------------------------------------------------------------------------
# READ VERBS (no lock)
# --------------------------------------------------------------------------
cmd_index() {
  local full="${1:-}"
  if [ "$full" = "--full" ] || [ "$full" = "full" ]; then
    cat "$INDEX"
  else
    # Research as a count unless asked in full: the catalog of research pages can
    # be hundreds of lines, and an agent reading this FIRST pays for every one.
    local research_count
    research_count=$(find "$PROCESSED/research" -name '*.md' ! -path '*/concepts/*' 2>/dev/null | wc -l | tr -d ' ')
    awk -v rc="$research_count" '
      /^## Research/ { print "## Research (" rc " pages — run: wiki index research)"; skip=1; next }
      /^## / { skip=0 }
      !skip { print }
    ' "$INDEX"
  fi
}

cmd_index_research() {
  local n
  n=$(find "$PROCESSED/research" -name '*.md' ! -path '*/concepts/*' 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" = "0" ] && { echo "(no research pages yet)"; return 0; }
  find "$PROCESSED/research" -name '*.md' ! -path '*/concepts/*' -exec basename {} .md \; | sort | sed 's/^/research\//'
}

cmd_search() {
  [ $# -ge 1 ] || die "usage: wiki search <text>"
  local pattern="$1"
  if [ -d "$PROCESSED" ]; then
    grep -ril --exclude-dir='_' -- "$pattern" "$PROCESSED" 2>/dev/null \
      | sed "s|^$PROCESSED/||; s|\.md$||" || true
  fi
  if [ -d "$RAW" ]; then
    grep -ril -- "$pattern" "$RAW" 2>/dev/null \
      | sed "s|^$RAW/|raw/|; s|\.md$||" || true
  fi
}

cmd_read() {
  [ $# -ge 1 ] || die "usage: wiki read <page-name>"
  local name="$1"
  case "$name" in
    index)  cat "$INDEX"; return ;;
    log)    cat "$LOG"; return ;;
    WIKI)   cat "$RULES"; return ;;
    raw/*)  local rp="$RAW/${name#raw/}.md"; [ -f "$rp" ] || die "no raw source '$name'"
            printf -- '--hash %s\n' "$(hash_of "$rp")"; printf '\n'; cat "$rp"; return ;;
  esac
  local p; p="$(path_of "$name")"
  [ -n "$p" ] || die "not on file: '$name'"
  printf -- '--hash %s\n' "$(hash_of "$p")"
  printf '\n'
  cat "$p"
}

cmd_rules() { cat "$RULES"; }

# --------------------------------------------------------------------------
# WRITE VERBS (always lock)
# --------------------------------------------------------------------------
# "Was this ever filed?" - on disk now, or in the repo's history. A page that was
# filed and later quarantined still counts: the log may record what happened to it.
was_filed() {
  [ -n "$(path_of "$1")" ] && return 0
  git_ready || return 1
  # ls-files would only see the pages tracked RIGHT NOW, and a quarantined page is not
  # tracked any more - its history is what proves it was filed once. So ask the log.
  # No pipe into grep -q here on purpose: grep -q exits on the first match, git gets
  # SIGPIPE, and under `set -o pipefail` the whole pipeline reads as a failure — the
  # check then says "never filed" about a page that is plainly in the history.
  local hit
  hit="$(git -C "$WIKI" log --all --max-count=1 --format=%H -- \
        "processed/*/$1.md" "processed/*/*/$1.md" 2>/dev/null)"
  [ -n "$hit" ] && return 0
  return 1
}

cmd_file() {
  # wiki file <folder> <name> --agent <agent> [--hash <hash>] [--summary "…"] [--aka "…"]
  # body on stdin. Writes page + index line + log line as one operation.
  local folder="" name="" agent="" hash="" summary="" aka=""
  while [ $# -gt 0 ]; do
    case "$1" in
      personal|business|research) folder="$1" ;;
      --agent)   agent="$2"; shift ;;
      --hash)    hash="$2"; shift ;;
      --summary) summary="$2"; shift ;;
      --aka)     aka="$2"; shift ;;
      raw)       folder="raw" ;;
      *)         [ -z "$name" ] && name="$1" ;;
    esac
    shift
  done
  [ -n "$folder" ] || die "usage: wiki file <personal|business|research|raw> <name> --agent <agent> [--hash <hash>]"
  [ -n "$name" ]   || die "usage: wiki file <folder> <name> --agent <agent>"
  [ -n "$agent" ]  || die "file needs --agent, so the log line names who filed it"
  check_agent "$agent"

  local body; body="$(cat)"

  if [ "$folder" = "raw" ]; then
    lock
    local rp="$RAW/$name.md"
    [ -f "$rp" ] && die "source already filed, choose a new slug: $name"
    mkdir -p "$RAW"
    printf '%s\n' "$body" > "$rp"
    printf -- '- [[raw/%s]] — source, filed %s\n' "$name" "$(today)" >> "$INDEX"
    printf '%s | %s | filed raw/%s\n' "$(today)" "$agent" "$name" >> "$LOG"
    commit_paths "$agent: $name" "$rp" "$INDEX" "$LOG"
    echo "filed raw/$name"
    return 0
  fi

  check_name "$name"
  case "$folder" in
    personal|business) ;;
    research) ;;
  esac
  lock

  local target="$PROCESSED/$folder/$name.md"

  # A name that exists in another folder is refused: names stay unique.
  local other; other="$(path_of "$name")"
  if [ -n "$other" ] && [ "$other" != "$target" ]; then
    die "name exists in another folder: $(printf '%s' "$other" | sed "s|$PROCESSED/||")"
  fi

  if [ -f "$target" ]; then
    [ -n "$hash" ] || die "page exists, read it first (wiki read $name), then file with --hash"
    local current; current="$(hash_of "$target")"
    [ "$hash" = "$current" ] || die "page changed since you read it, read it again"
  fi

  mkdir -p "$(dirname "$target")"
  if [ -z "$summary" ]; then
    summary="$(printf '%s' "$body" | awk 'BEGIN{RS="\n\n"} /^[^#]/ && length($0)>0 {gsub(/\n/," "); print substr($0,1,120); exit}')"
    [ -n "$summary" ] || summary="(no summary yet)"
  fi

  printf '%s\n' "$body" > "$target"

  if [ -f "$target" ] && grep -q "\[\[$name\]\]" "$INDEX" 2>/dev/null; then
    :                       # index line already there (an update, not a filing)
  else
    local heading
    case "$folder" in
      personal) heading="## Personal" ;;
      business) heading="## Business" ;;
      research) heading="## Research" ;;
    esac
    if ! grep -q "^$heading" "$INDEX" 2>/dev/null; then
      printf '\n%s\n\n' "$heading" >> "$INDEX"
    fi
    local line; line="$(index_line_for "$name" "$folder" "$summary" "$aka")"
    printf '%s\n' "$line" >> "$INDEX"
  fi
  printf '%s | %s | filed %s/%s\n' "$(today)" "$agent" "$folder" "$name" >> "$LOG"
  commit_paths "$agent: $name" "$target" "$INDEX" "$LOG"
  printf '%s\n' "$(hash_of "$target")"
  echo "filed $folder/$name" >&2
}

cmd_reindex() {
  lock
  local tmp; tmp="$(mktemp)"
  printf '# Wiki index\n\nOne line per page, each a link. Agents read this FIRST.\n' > "$tmp"
  for folder in personal business research; do
    local count
    count=$(find "$PROCESSED/$folder" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
    [ "$count" = "0" ] && continue
    case "$folder" in
      personal) printf '\n## Personal\n\n' >> "$tmp" ;;
      business) printf '\n## Business\n\n' >> "$tmp" ;;
      research) printf '\n## Research\n\n' >> "$tmp" ;;
    esac
    find "$PROCESSED/$folder" -maxdepth 1 -name '*.md' | sort | while read -r p; do
      n="$(basename "$p" .md)"
      s="$(awk 'BEGIN{RS="\n\n"} /^[^#]/ && length($0)>0 {gsub(/\n/," "); print substr($0,1,120); exit}' "$p")"
      printf -- '- [[%s]] — %s\n' "$n" "${s:-(no summary yet)}" >> "$tmp"
    done
  done
  local cc
  cc=$(find "$PROCESSED/research/concepts" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
  if [ "$cc" != "0" ]; then
    printf '\n## Concepts\n\n' >> "$tmp"
    find "$PROCESSED/research/concepts" -maxdepth 1 -name '*.md' | sort | while read -r p; do
      n="$(basename "$p" .md)"
      printf -- '- [[%s]]\n' "$n" >> "$tmp"
    done
  fi
  local rc
  rc=$(find "$RAW" -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
  if [ "$rc" != "0" ]; then
    printf '\n## Raw sources (%s)\n\n' "$rc" >> "$tmp"
    find "$RAW" -name '*.md' | sort | while read -r p; do
      printf -- '- [[raw/%s]]\n' "$(basename "$p" .md)" >> "$tmp"
    done
  fi
  mv "$tmp" "$INDEX"
  printf '%s | builder | reindex: %s pages\n' "$(today)" "$(find "$PROCESSED" -name '*.md' | wc -l | tr -d ' ')" >> "$LOG"
  commit_paths "builder: index.md" "$INDEX" "$LOG"
  echo "index rebuilt"
}

cmd_log() {
  # wiki log --agent <agent> "what happened" [--pages a,b]
  local agent="" text="" pages=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --agent) agent="$2"; shift ;;
      --pages) pages="$2"; shift ;;
      *) [ -z "$text" ] && text="$1" ;;
    esac
    shift
  done
  [ -n "$agent" ] || die "log needs --agent"
  [ -n "$text" ]  || die "log needs something to say"
  check_agent "$agent"
  if [ -n "$pages" ]; then
    local p
    for p in ${pages//,/ }; do
      was_filed "$p" || die "log refuses page names that were never filed: '$p' (not on disk, and git history does not have it either)"
    done
  fi
  lock
  printf '%s | %s | %s%s\n' "$(today)" "$agent" "$text" "${pages:+ [pages: $pages]}" >> "$LOG"
  commit_paths "$agent: log" "$LOG"
  echo "logged"
}

cmd_delete() {
  [ $# -ge 1 ] || die "usage: wiki delete <page-name> --agent <agent>"
  local name="$1" agent="builder"
  [ "${2:-}" = "--agent" ] && agent="$3"
  case "$name" in raw/*) die "raw/ is never removed"; esac
  check_name "$name"
  check_agent "$agent"
  lock
  local p; p="$(path_of "$name")"
  [ -n "$p" ] || die "not on file: '$name'"
  local folder; folder="$(basename "$(dirname "$p")")"
  mkdir -p "$PROCESSED/_deleted"
  local dest="$PROCESSED/_deleted/$name.$(date +%Y%m%d-%H%M%S).md"
  mv "$p" "$dest"
  # quarantine, then drop its index line: nothing in this system destroys a page
  grep -v "\[\[$name\]\]" "$INDEX" > "$INDEX.tmp" && mv "$INDEX.tmp" "$INDEX"
  printf '%s | %s | quarantined %s (was %s/)\n' "$(today)" "$agent" "$name" "$folder" >> "$LOG"
  commit_paths "$agent: $name (deleted)" "$dest" "$p" "$INDEX" "$LOG"
  echo "quarantined to $dest"
}

cmd_snapshot() {
  # wiki snapshot [--label "opening snapshot"] [--agent A] [--allow-empty]
  # The nightly jobs and the dashboard's second button both come through here, so
  # the commit happens under the same lock as every verb. Exit 3 means busy: the
  # caller must be able to tell "nothing to do" from "someone else is writing".
  local label="snapshot" agent="mirai" allow_empty=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --label) label="$2"; shift ;;
      --agent) agent="$2"; shift ;;
      --allow-empty) allow_empty=1 ;;
      *) die "usage: wiki snapshot [--label TEXT] [--agent A] [--allow-empty]" ;;
    esac
    shift
  done
  check_agent "$agent"
  lock_for_snapshot
  git_ready || die "the wiki is not a git repository yet: run  git -C $WIKI init  first"

  git -C "$WIKI" add -A >/dev/null 2>&1 || die "git add -A failed"
  if git -C "$WIKI" diff --cached --quiet; then
    if [ "$allow_empty" = 0 ]; then
      echo "nothing to snapshot"
      return 0
    fi
    git -C "$WIKI" -c user.name=MIRAI -c user.email=mirai@localhost \
        commit -q --allow-empty -m "$agent: $label" || die "the closing commit failed"
    echo "committed (empty: the day is still marked)"
    return 0
  fi
  local n; n="$(git -C "$WIKI" diff --cached --name-only | wc -l | tr -d ' ')"
  git -C "$WIKI" -c user.name=MIRAI -c user.email=mirai@localhost \
      commit -q -m "$agent: $label" || die "the snapshot commit failed"
  echo "committed $n path(s)"
}

# --------------------------------------------------------------------------
usage() {
  cat <<'USAGE'
wiki — the crew's memory

  wiki index [--full]                 the catalog (Research as a count unless --full)
  wiki index research                 list the research pages
  wiki search <text>                  literal text match across pages and raw sources
  wiki read <name|index|log|WIKI>     a page, preceded by its sha256
  wiki rules                          the rulebook (WIKI.md)

  wiki file <folder> <name> --agent A [--hash H] [--summary "…"]   (body on stdin)
  wiki reindex                        rebuild index.md from the files
  wiki log --agent A "text" [--pages a,b]
  wiki delete <name> [--agent A]      quarantine a page (never raw/)
  wiki snapshot [--label TEXT] [--allow-empty] [--agent A]
                                      commit whatever is loose, under the lock

Folders: personal | business | research | raw
USAGE
}

main() {
  [ $# -ge 1 ] || { usage; exit 1; }
  local verb="$1"; shift
  case "$verb" in
    index)   if [ "${1:-}" = "research" ]; then cmd_index_research; else cmd_index "${1:-}"; fi ;;
    search)  cmd_search "$@" ;;
    read)    cmd_read "$@" ;;
    rules)   cmd_rules ;;
    file)    cmd_file "$@" ;;
    reindex) cmd_reindex ;;
    log)     cmd_log "$@" ;;
    delete)  cmd_delete "$@" ;;
    snapshot) cmd_snapshot "$@" ;;
    help|-h|--help) usage ;;
    *) usage; exit 1 ;;
  esac
}

main "$@"
