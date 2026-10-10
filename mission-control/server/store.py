"""Where MIRAI's own state lives: one SQLite database under ~/mirai/data/.

No routes here. Every other module writes through this layer, so there is one
shape for settings, one shape for the audit trail and one place to look when a
row is missing.

Two traps this file engineers around, both found the hard way:
  * ensure() must never run while a connection is being opened, or the obvious
    "take a lock, call con(), con() calls ensure()" version deadlocks on the
    first request and looks like a hang rather than an error. The core tables
    are created in bootstrap(), outside the lock path.
  * execute() returns (lastrowid, rowcount), not "the row id": an UPDATE or a
    DELETE has no row id and lastrowid is stale there.
"""
from __future__ import annotations

import getpass
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

MIRAI_DIR = Path(os.environ.get("MIRAI_DIR", str(Path.home() / "mirai"))).expanduser()
DATA_DIR = Path(os.environ.get("MIRAI_DATA_DIR", str(MIRAI_DIR / "data"))).expanduser()
DB_PATH = DATA_DIR / "mirai.db"

_local = threading.local()
_schema_done: set[str] = set()
_schema_lock = threading.Lock()

CORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY,
  at REAL NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  detail TEXT
);
CREATE TABLE IF NOT EXISTS agent_codes(
  profile TEXT PRIMARY KEY,
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS avatars(
  owner TEXT PRIMARY KEY,          -- an agent code, or the string 'operator'
  kind TEXT NOT NULL,              -- library | upload | default
  file_name TEXT,
  library_id TEXT,
  updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS turns(
  id INTEGER PRIMARY KEY,
  at REAL NOT NULL,
  agent TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'mirai',
  conversation TEXT,
  role TEXT NOT NULL,              -- you | agent
  text TEXT NOT NULL,
  ms REAL,
  files TEXT                       -- JSON list of {name,type,size,url}
);
CREATE INDEX IF NOT EXISTS idx_turns_agent ON turns(agent, at);
"""

SETTINGS_DEFAULTS = {
    "display_name": "",
    "operator_name": getpass.getuser(),
    "timezone": "UTC",
    "voice_engine": "local",
}

# Operator name resolution: what the crew calls you, read from THEIR files.
_USER_NAME_PATTERNS = (
    "Name:", "User's name is", "Owner:", "Operator:",
)


def con() -> sqlite3.Connection:
    """A connection per thread. WAL, because two readers and a writer is normal here."""
    c = getattr(_local, "con", None)
    if c is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.DatabaseError:
            pass
        _local.con = c
    return c


def ensure(schema_sql: str, name: str) -> None:
    """Apply one CREATE TABLE IF NOT EXISTS block, once per process.

    Called by modules as they are imported, never from inside con().
    """
    with _schema_lock:
        if name in _schema_done:
            return
        con().executescript(schema_sql)
        con().commit()
        _schema_done.add(name)


def bootstrap() -> None:
    """Core tables + defaults. Safe to call on every start."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ensure(CORE_SCHEMA, "core")
    for k, v in SETTINGS_DEFAULTS.items():
        execute("INSERT OR IGNORE INTO settings(key, value, updated_at) VALUES(?,?,?)",
                (k, json.dumps(v), time.time()))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def query(sql: str, args: tuple | list = ()) -> list[dict]:
    cur = con().execute(sql, tuple(args))
    return [dict(r) for r in cur.fetchall()]


def one(sql: str, args: tuple | list = ()):
    cur = con().execute(sql, tuple(args))
    row = cur.fetchone()
    return dict(row) if row else None


def execute(sql: str, args: tuple | list = ()) -> tuple[int | None, int]:
    c = con()
    cur = c.execute(sql, tuple(args))
    c.commit()
    return cur.lastrowid, cur.rowcount


def executemany(sql: str, seq) -> int:
    c = con()
    cur = c.executemany(sql, list(seq))
    c.commit()
    return cur.rowcount


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def settings() -> dict:
    rows = query("SELECT key, value FROM settings")
    out = dict(SETTINGS_DEFAULTS)
    for r in rows:
        try:
            out[r["key"]] = json.loads(r["value"])
        except Exception:
            out[r["key"]] = r["value"]
    return out


def save_settings(changes: dict) -> dict:
    """Write only the keys given."""
    now = time.time()
    for k, v in changes.items():
        execute(
            "INSERT INTO settings(key, value, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (k, json.dumps(v), now),
        )
    return settings()


def operator_name_from_hermes() -> str | None:
    """Read what the crew calls the owner, out of the crew's own files.

    ~/.hermes/memories/USER.md first, then ~/.hermes/SOUL.md. The line usually
    runs on past the name, so stop at the first full stop.
    """
    hermes = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
    for path in (hermes / "memories" / "USER.md", hermes / "SOUL.md"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            # Markdown noise first: "**Name:** Afrizal." is a common shape in USER.md.
            stripped = line.strip().lstrip("#->* ").replace("**", "").strip()
            for pat in _USER_NAME_PATTERNS:
                pat_clean = pat.replace("**", "")
                if stripped.startswith(pat_clean):
                    value = stripped[len(pat_clean):].strip().strip(":").strip()
                    value = value.split(".")[0].strip()      # the line runs on past the name
                    if value and not value.startswith("http"):
                        return value[:60]
    return None


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
def audit(actor: str, action: str, detail: dict | None = None) -> None:
    execute("INSERT INTO audit(at, actor, action, detail) VALUES(?,?,?,?)",
            (time.time(), actor, action, json.dumps(detail or {}, ensure_ascii=False)))


def recent_audit(limit: int = 50) -> list[dict]:
    rows = query("SELECT at, actor, action, detail FROM audit ORDER BY id DESC LIMIT ?", (limit,))
    for r in rows:
        try:
            r["detail"] = json.loads(r["detail"] or "{}")
        except Exception:
            r["detail"] = {}
    return rows
