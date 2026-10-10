#!/usr/bin/env bash
# fixture.sh — the throwaway crew the tests run against.
#
# WHY THIS FILE EXISTS
#   prove.sh and smoke.sh both need a ~/.hermes to find. Without one, /api/agents
#   answers with an empty fleet and the smoke test's agent loop dies on an empty
#   list - a test that fails because of its own missing fixture teaches nothing.
#   /tmp does not survive a reboot, so the fixture is built by the test, every run.
#
# WHAT IT MAKES (all inside $HOME, which the callers set to a throwaway)
#   $HOME/.hermes/SOUL.md                     the default profile's identity
#   $HOME/.hermes/config.yaml                 its model, so the fleet shows one
#   $HOME/.hermes/profiles/research/...       a second profile, with a cron store
#   $HOME/mirai/data/                         the state dir the server writes to
#
# IT DELIBERATELY MAKES NO REAL CREDENTIALS: no auth.json, no token, and the cron
#   store uses an absolute path that only exists under $HOME.
#
# Usage:  HOME=/tmp/fakehome MIRAI_DIR=/tmp/fakehome/mirai bash fixture.sh
set -u

# Refuse to build a "throwaway" crew anywhere but /tmp: this script mkdirs and
# overwrites, and the one dir it must never be pointed at is a real ~/.hermes.
H="${HERMES_HOME:-$HOME/.hermes}"
D="${MIRAI_DIR:-$HOME/mirai}"
case "$H:$D" in
  /tmp/*:/tmp/*) : ;;
  *)
    echo "fixture.sh refuses to run against $H — point HOME (or MIRAI_DIR) at /tmp first." >&2
    echo "The tests do this for you; if you really mean it, set MIRAI_FIXTURE_OK=1." >&2
    [ "${MIRAI_FIXTURE_OK:-0}" = 1 ] || exit 2
    ;;
esac

mkdir -p "$D"/{data,data/avatars,data/chat-files,data/docs,data/file-backups,data/archive,docs,proj}

mkdir -p "$H"
cat > "$H/SOUL.md" <<'EOF'
Your name is Executor.

You are the orchestrator of the owner's fleet, and the agent the owner talks to.
EOF
cat > "$H/config.yaml" <<'EOF'
model:
  default: gpt-5.4-mini
  provider: openai
EOF

mkdir -p "$H/profiles/research/cron" "$H/profiles/research/memories"
cat > "$H/profiles/research/SOUL.md" <<'EOF'
Your name is Research.

You are the intelligence of the owner's fleet: you find things out with live
sources and say where each fact came from.
EOF
cat > "$H/profiles/research/config.yaml" <<'EOF'
model:
  default: gpt-5.4-mini
  provider: openai
EOF

# The cron store as the CLI writes it: an object with a jobs list, not a bare list.
cat > "$H/profiles/research/cron/jobs.json" <<EOF
{
  "jobs": [
    {
      "id": "fixture-dropbox",
      "name": "wiki-dropbox",
      "schedule": {"expr": "*/30 * * * *"},
      "prompt": "Drain raw/_inbox through INGEST, then heartbeat. [SILENT] if nothing.",
      "enabled": true
    }
  ]
}
EOF

# roles.json ships with the package and install-mac.sh copies it into the state
# dir; without it /api/workforce/library answers empty, which would look like a bug.
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$PROJ/data/roles.json" ]; then
  cp "$PROJ/data/roles.json" "$D/data/roles.json"
fi

printf 'fixture ready: %s (profiles: %s)\n' "$H" "$(ls "$H/profiles" 2>/dev/null | tr '\n' ' ')"
