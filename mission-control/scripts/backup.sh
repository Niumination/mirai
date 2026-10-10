#!/usr/bin/env bash
# Keep a copy. Runs nightly from launchd (see install-mac.sh).
#
# What is snapshotted: our data folder, the dashboard file, and the editable
# files of every Hermes profile (SOUL.md, USER.md, MEMORY.md). NOT the session
# databases, NOT the caches, and never data/secrets.env — it lives inside the
# folder being copied, and a backup is the easiest place to leak a key from.
#
# Hard links against the previous snapshot, so twenty snapshots cost about as
# much as one.
set -euo pipefail

STAMP="$(date +%Y%m%d-%H%M%S)"
# Two backups in the same second must not share a folder: the second one would
# write into the first one's snapshot and the pair would look like a single copy.
_n=1
while [ -e "${MIRAI_BACKUP_DIR:-$HOME/mirai-backups}/$STAMP" ]; do
  _n=$((_n + 1)); STAMP="$(date +%Y%m%d-%H%M%S)-$_n"
done
MIRAI_DIR="${MIRAI_DIR:-$HOME/mirai}"
HERMES="${HERMES_HOME:-$HOME/.hermes}"
DEST="${MIRAI_BACKUP_DIR:-$HOME/mirai-backups}/$STAMP"
PREV="$(ls -1d "${MIRAI_BACKUP_DIR:-$HOME/mirai-backups}"/*/ 2>/dev/null | tail -1 || true)"
KEEP=30

mkdir -p "$DEST"

linkable() {  # copy with hard links against $PREV when possible
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [ -n "$PREV" ] && [ -e "${PREV}${dst#${DEST}/}" ]; then
    cp -al "${PREV}${dst#${DEST}/}" "$dst" 2>/dev/null || cp -a "$src" "$dst"
  else
    cp -a "$src" "$dst"
  fi
}

# 1. our own data, minus secrets
if [ -d "$MIRAI_DIR/data" ]; then
  ( cd "$MIRAI_DIR" && find data -type f ! -name 'secrets.env' -print0 )
  while IFS= read -r -d '' rel; do
    linkable "$MIRAI_DIR/$rel" "$DEST/$rel"
  done < <( cd "$MIRAI_DIR" && find data -type f ! -name 'secrets.env' -print0 )
fi

# 2. the dashboard file (it is an artifact we want to be able to diff)
[ -f "$MIRAI_DIR/dashboard.html" ] && linkable "$MIRAI_DIR/dashboard.html" "$DEST/dashboard.html"

# 3. the fleet's editable files. Session databases are deliberately left out.
mkdir -p "$DEST/hermes"
copy_profile() {
  local home="$1" label="$2"
  for f in SOUL.md config.yaml memories/USER.md memories/MEMORY.md; do
    [ -f "$home/$f" ] || continue
    linkable "$home/$f" "$DEST/hermes/$label/$f"
  done
}
[ -d "$HERMES" ] && copy_profile "$HERMES" "default"
if [ -d "$HERMES/profiles" ]; then
  for p in "$HERMES"/profiles/*/; do
    [ -d "$p" ] || continue
    copy_profile "$p" "$(basename "$p")"
  done
fi

# 4. a way back that does not depend on remembering how
cat > "$DEST/restore.sh" <<'RESTORE'
#!/usr/bin/env bash
# Put this snapshot back. Usage: ./restore.sh [--data] [--hermes]   (default: both)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MIRAI_DIR="${MIRAI_DIR:-$HOME/mirai}"
HERMES="${HERMES_HOME:-$HOME/.hermes}"
do_data=1; do_hermes=1
[ "$#" -gt 0 ] && do_data=0 && do_hermes=0
for a in "$@"; do
  [ "$a" = "--data" ] && do_data=1
  [ "$a" = "--hermes" ] && do_hermes=1
done
if [ "$do_data" = 1 ] && [ -d "$HERE/data" ]; then
  echo "restoring $MIRAI_DIR/data from $HERE/data"
  mkdir -p "$MIRAI_DIR"
  rsync -a --backup --suffix=.before-restore "$HERE/data/" "$MIRAI_DIR/data/" 2>/dev/null || \
    cp -a "$HERE/data/." "$MIRAI_DIR/data/"
fi
if [ "$do_hermes" = 1 ] && [ -d "$HERE/hermes" ]; then
  for label in "$HERE"/hermes/*/; do
    name="$(basename "$label")"
    if [ "$name" = "default" ]; then home="$HERMES"; else home="$HERMES/profiles/$name"; fi
    [ -d "$home" ] || continue
    echo "restoring profile $name"
    cp -a "$label"SOUL.md "$home/" 2>/dev/null || true
    cp -a "$label"memories "$home/" 2>/dev/null || true
    cp -a "$label"config.yaml "$home/" 2>/dev/null || true
  done
fi
echo "done. Restart the service: ~/mirai/mission-control/scripts/restart.sh"
RESTORE
chmod +x "$DEST/restore.sh"

# 5. keep the last $KEEP, delete older
# macOS ships bash 3.2, which has no mapfile: read the list line by line instead,
# so this script works with /bin/bash as well as any newer bash from Homebrew.
OLD=()
while IFS= read -r dir; do OLD+=("$dir"); done < <(ls -1d "${MIRAI_BACKUP_DIR:-$HOME/mirai-backups}"/*/ 2>/dev/null | sort -r | tail -n +$((KEEP + 1)))
for d in "${OLD[@]:-}"; do
  [ -n "$d" ] && rm -rf "$d"
done

# 6. WAL-safe copy proof and the report
echo "snapshot: $DEST"
if command -v sqlite3 >/dev/null 2>&1 && [ -f "$MIRAI_DIR/data/mirai.db" ]; then
  # The database is live and in WAL mode: copying the .db alone can catch it mid
  # write. sqlite3's own .backup is the safe way, so the snapshot gets one too.
  sqlite3 "$MIRAI_DIR/data/mirai.db" ".backup '$DEST/data/mirai.db.consistent'"
fi
du -sh "$DEST" | awk '{print "size:", $1}'
if [ -n "$PREV" ]; then
  echo "new disk used against the previous snapshot:"
  du -sh --exclude-from=- "$DEST" 2>/dev/null <<< "$PREV" || echo "  (GNU du only; skipped on macOS)"
fi
echo "files: $(find "$DEST" -type f | wc -l | tr -d ' ')"
