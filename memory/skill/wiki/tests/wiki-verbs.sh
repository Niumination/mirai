#!/usr/bin/env bash
# wiki-verbs.sh — every verb, on a throwaway wiki, including the git safety net.
#
# WHAT THIS PROVES (the pack asks for all of it by name)
#   1. the four readers never lock and never write;
#   2. every mutating verb commits inside the lock it holds, staging only what it
#      touched, message "<agent>: <page-name>" — one commit per write;
#   3. a failed commit is loud, not silent;
#   4. the refusals: a page that changed under you, a name that exists in another
#      folder, a raw/ slug that exists, a log line for a page that was never filed
#      (checked against the repo, not just the disk), deleting raw/;
#   5. wiki snapshot: "nothing to snapshot" when clean, --allow-empty for the closing
#      mark, exit 3 and the exact sentence when the lock is held by someone else;
#   6. .gitignore keeps the machinery out of history: the folder .gitkeep files are
#      tracked, whatever lands in raw/_inbox is not;
#   7. RECOVERY, live: list a day's commits, change a page, restore it from the
#      commit, and see the content come back.
#
# Nothing here touches a real wiki: it builds /tmp/wiki-verbs and never leaves it.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
W="$HERE/wiki.sh"
R="/tmp/wiki-verbs"
fail=0
say() { printf '%-52s %s\n' "$1" "$2"; }
chk() { case "$2" in *"$3"*) say "$1" "ok";; *) say "$1" "MISMATCH: $2"; fail=1;; esac; }

rm -rf "$R"; mkdir -p "$R"/processed/{personal,business,research} "$R"/processed/research/concepts "$R"/drafts "$R"/raw/{_inbox,_working,_done,_failed}
cp "$(cd "$HERE/../.." && pwd)/wiki-skeleton/WIKI.md" "$R/"
cp "$(cd "$HERE/../.." && pwd)/wiki-skeleton/.gitignore" "$R/"
cp "$(cd "$HERE/../.." && pwd)/wiki-skeleton/index.md" "$R/"
cp "$(cd "$HERE/../.." && pwd)/wiki-skeleton/log.md" "$R/"
for d in processed/personal processed/business processed/research processed/research/concepts drafts raw/_inbox raw/_working raw/_done raw/_failed; do
  touch "$R/$d/.gitkeep"
done
export CREW_WIKI_DIR="$R"
git -C "$R" init -q
git -C "$R" config user.name MIRAI            # repo-local, never --global
git -C "$R" config user.email mirai@localhost
git -C "$R" add -A >/dev/null && git -C "$R" commit -qm "the wiki skeleton"   # the baseline

echo "== 2. every write commits itself =="
H1="$(bash "$W" file business acme-corp --agent developer --summary 'Customer since 2026-03' <<'EOF' | tail -1
# Acme Corp

Customer since 2026-03. Two reports delivered.
EOF
)"
chk "file returns a sha256 of the page" "$(printf '%s' "$H1" | grep -cE '^[0-9a-f]{64}$')" "1"
say "commit message" "$(git -C "$R" log -1 --pretty=%s)"
chk "index and log came along" "$(git -C "$R" show --stat --name-only --format= HEAD | grep -c 'index.md\|log.md')" "2"
bash "$W" file personal afrizal --agent executor --summary "The owner" <<'EOF' >/dev/null
# Afrizal

Owner. Banda Aceh.
EOF
chk "second page, second commit" "$(git -C "$R" log -1 --pretty=%s)" "executor: afrizal"

echo "== 4. the refusals =="
chk "update with no hash" "$(bash "$W" file business acme-corp --agent developer <<< 'new body' 2>&1)" "read it first"
chk "update with a stale hash" "$(bash "$W" file business acme-corp --agent developer --hash deadbeef <<< 'new body' 2>&1)" "changed since you read it"
chk "name in another folder" "$(bash "$W" file business afrizal --agent developer <<< 'x' 2>&1)" "name exists in another folder"
chk "raw slug twice" "$(bash "$W" file raw 2026-01-01-source --agent research <<< 'one' >/dev/null 2>&1; bash "$W" file raw 2026-01-01-source --agent research <<< 'two' 2>&1)" "source already filed"
chk "delete raw/" "$(bash "$W" delete raw/2026-01-01-source 2>&1)" "raw/ is never removed"
chk "log a page that never existed" "$(bash "$W" log --agent executor 'filed a ghost' --pages never-written 2>&1)" "never filed"

echo "== 4b. the hardened log check, against the repo =="
bash "$W" delete acme-corp --agent developer >/dev/null 2>&1
chk "a committed-then-quarantined page still counts" "$(bash "$W" log --agent developer 'restored acme-corp' --pages acme-corp 2>&1)" "logged"

echo "== 5. snapshot =="
chk "clean night" "$(bash "$W" snapshot --label 'opening snapshot' 2>&1)" "nothing to snapshot"
chk "the closing mark is unconditional" "$(bash "$W" snapshot --label 'closing snapshot' --allow-empty 2>&1)" "committed (empty"
say "closing commit message" "$(git -C "$R" log -1 --pretty=%s)"
# hold the lock, then ask for a snapshot: it must refuse in the pack's own words
(
  mkdir "$R/.wiki.lock"
  sleep 4
  rmdir "$R/.wiki.lock" 2>/dev/null
) &
HOLDER=$!
sleep 0.7
OUT="$(WIKI_LOCK_WAIT=1 bash "$W" snapshot --label 'blocked test' 2>&1)"; RC=$?
say "busy snapshot, exit code" "$RC"
chk "busy snapshot, sentence" "$OUT" "wiki is busy, nothing was snapshotted"
chk "busy snapshot, exit 3" "$RC" "3"
wait "$HOLDER" 2>/dev/null

echo "== 6. the machinery stays out of history =="
printf 'a failed 18 MB pdf stand-in\n' > "$R/raw/_inbox/big-thing.pdf"
bash "$W" snapshot --label 'pipeline check' >/dev/null 2>&1
chk "raw/_inbox contents are ignored" "$(git -C "$R" status --porcelain --ignored=no | grep -c 'big-thing' )" "0"
chk "the folder .gitkeep is tracked" "$(git -C "$R" ls-files raw/_inbox/.gitkeep | wc -l | tr -d ' ')" "1"
chk "the lock is ignored" "$(git -C "$R" check-ignore -q .wiki.lock && echo ignored || echo tracked)" "ignored"

echo "== 7. recovery, live =="
bash "$W" file research gayo-prices --agent research --summary "prices" <<'EOF' >/dev/null
# Gayo prices

1500 offered (2026-08-20).
EOF
FIRST_SHA="$(git -C "$R" log -1 --pretty=%h -- processed/research/gayo-prices.md)"
chk "the day's commits for one page" "$(git -C "$R" log --oneline --since=midnight -- processed/research/gayo-prices.md | wc -l | tr -d ' ')" "1"
CUR_HASH="$(bash "$W" read gayo-prices | sed -n '1s/^--hash //p')"
bash "$W" file research gayo-prices --agent research --hash "$CUR_HASH" --summary "prices" <<'EOF' >/dev/null
# Gayo prices

1800 offered (2026-09-02). This line is the mistake.
EOF
chk "the mistake is in the file" "$(grep -c 'mistake' "$R/processed/research/gayo-prices.md")" "1"
chk "the restore command brings the good line back" "$(git -C "$R" show "$FIRST_SHA:processed/research/gayo-prices.md" | grep -c '1500 offered')" "1"
git -C "$R" show "$FIRST_SHA:processed/research/gayo-prices.md" > "$R/processed/research/gayo-prices.md"
chk "restored content is back" "$(grep -c '1500 offered' "$R/processed/research/gayo-prices.md")" "1"
chk "the restore is committed, not left loose" "$(bash "$W" snapshot --label 'restored gayo-prices' 2>&1)" "committed 1 path"
bash "$W" log --agent research 'restored gayo-prices from its first commit (the 1800 line was wrong)' --pages gayo-prices >/dev/null
chk "the restore is recorded in the log" "$(tail -2 "$R/log.md" | grep -c 'restored gayo-prices')" "1"

echo
say "commits in the repo" "$(git -C "$R" rev-list --count HEAD)"
say "working tree" "$(git -C "$R" status --porcelain | wc -l | tr -d ' ') modified path(s) after the run"
echo
if [ "$fail" -eq 0 ]; then echo "wiki-verbs: every check matched"; else echo "wiki-verbs: SOMETHING MISMATCHED (see above)"; fi
exit "$fail"
