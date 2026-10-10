"""roster.py — who is on this machine, read from the HOST Hermes install.

READ ONLY. Nothing in this file writes under ~/.hermes.

Discovery is done from the disk, not from a hardcoded list: an agent that was
removed must disappear from the dashboard. A folder only counts as a profile
when it holds config.yaml, SOUL.md or profile.yaml — on some platforms a
deleted profile's folder outlives the delete, and counting it keeps a ghost on
the page.

Tolerant by design: the shape of Hermes' own state.db has moved between
versions, so the readers below introspect the schema and adapt rather than
asserting table names. A seat whose files cannot be read is `unreachable`,
never an exception.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import store

HOME = Path.home()
HERMES = Path(os.environ.get("HERMES_HOME", str(HOME / ".hermes"))).expanduser()

STATUS_WORDS = ("working", "active", "ready", "unreachable")
STATUS_LABELS = {
    "working": "Working",
    "active": "Active today",
    "ready": "Ready",
    "unreachable": "Unreachable",
}

_CACHE_TTL = 2.0
_cache: dict = {"at": 0.0, "value": None}

# Two-letter codes are written down the first time a profile is seen and reused
# for ever: portraits and history are keyed by them.
_VOWELS = set("AEIOU")

BUILDINGS = {
    "working": "HQ",
    "active": "Studio",
    "ready": "Cabin",
    "unreachable": "Depot",
}


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
def _home(profile: str) -> Path:
    """The default profile's home IS HERMES; every other profile lives under profiles/."""
    if profile in ("default", "", None):
        return HERMES
    return HERMES / "profiles" / profile


def _looks_like_profile(p: Path) -> bool:
    return any((p / n).exists() for n in ("config.yaml", "SOUL.md", "profile.yaml"))


def profiles() -> list[str]:
    """Every profile that actually exists on disk, default first."""
    out: list[str] = []
    if _looks_like_profile(HERMES):
        out.append("default")
    pdir = HERMES / "profiles"
    if pdir.is_dir():
        for child in sorted(pdir.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if _looks_like_profile(child):
                out.append(child.name)
    return out


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Names, roles, models
# ---------------------------------------------------------------------------
_NAME_PATTERNS = (
    re.compile(r"^\s*Your name is ([A-Za-z0-9][A-Za-z0-9 _\-]{0,40}?)\.", re.M),
    re.compile(r"^\s*You are the ([A-Za-z0-9][A-Za-z0-9 _\-]{0,40}?)[,.]", re.M),
    re.compile(r"^\s*You are ([A-Z][A-Za-z0-9 _\-]{1,40}?)\.", re.M),
)


def _titleise(folder: str) -> str:
    """A fresh install has factory SOUL text, so the folder name IS the name."""
    return " ".join(w.capitalize() if w.islower() else w for w in re.split(r"[-_ ]+", folder) if w)


def _display_name(raw: str) -> str:
    """An all-caps SOUL line is a shouty identity, not a title: EXECUTOR -> Executor."""
    if raw.isupper():
        return " ".join(w.capitalize() for w in raw.split())
    return raw


def name_from_soul(profile: str) -> tuple[str, bool]:
    """(name, found_in_soul). A heading is never a name."""
    text = _read_text(_home(profile) / "SOUL.md")
    for pat in _NAME_PATTERNS:
        m = pat.search(text)
        if m:
            candidate = m.group(1).strip()
            # "You are the orchestrator of..." must not become the name.
            if candidate.lower() in ("owner", "user", "operator", "agent"):
                continue
            if re.match(r"^[A-Za-z0-9 _\-]{2,32}$", candidate):
                return candidate, True
    return _titleise(profile), False


def role_from_soul(profile: str) -> str | None:
    """The agent's own line about itself, from its SOUL — a whole sentence."""
    text = _read_text(_home(profile) / "SOUL.md")
    # Its own role sentence usually sits right after the name line.
    m = re.search(r"(?:Your name is|You are) [^\n]*?\n+(.{20,400}?)(?:\n\s*\n|\Z)", text, re.S)
    if m:
        sentence = " ".join(m.group(1).split())
        if sentence and not sentence.startswith("#"):
            first = re.split(r"(?<=[.!?])\s+", sentence)[0]
            if 12 <= len(first) <= 400:
                return first
    return None


def description_from_profile_yaml(profile: str) -> str | None:
    """profile.yaml holds a description when it exists at all, never the name."""
    text = _read_text(_home(profile) / "profile.yaml")
    if not text:
        return None
    m = re.search(r"^\s*description:\s*(.+)$", text, re.M)
    if m:
        value = m.group(1).strip().strip('"').strip("'")
        return value or None
    return None


def model_from_config(profile: str) -> str:
    """model.default in that profile's config.yaml.

    No YAML parser here (and this build bans installing one), so scan for the
    line rather than pretending to parse the file.
    """
    text = _read_text(_home(profile) / "config.yaml")
    if not text:
        return ""
    # model: followed by an indented default: two lines later, or inline
    m = re.search(r"^model:\s*\n(?:[ \t]+.*\n)*?[ \t]+default:\s*([^\n#]+)", text, re.M)
    if m:
        return m.group(1).strip().strip('"').strip("'")
    m = re.search(r"^model:\s*([A-Za-z0-9_\-./:]+)\s*$", text, re.M)
    if m:
        return m.group(1).strip()
    m = re.search(r"^\s*default_model:\s*([^\n#]+)", text, re.M)
    if m:
        return m.group(1).strip().strip('"').strip("'")
    return ""


# ---------------------------------------------------------------------------
# Codes: two letters, with a tie break and a memory
# ---------------------------------------------------------------------------
def _candidates(name: str) -> list[str]:
    letters = [c for c in re.sub(r"[^A-Za-z]", "", name).upper()]
    if not letters:
        letters = ["A", "X"]
    first = letters[0]
    out = [first + letters[1]] if len(letters) > 1 else [first + "X"]
    consonants = [c for c in letters[1:] if c not in _VOWELS]
    for c in consonants:
        out.append(first + c)
    for c in [c for c in letters[1:]]:
        out.append(first + c)
    out.append(first + "X")
    for d in range(1, 10):
        out.append(f"{first}{d}")
    # de-dup, keep order
    seen, uniq = set(), []
    for c in out:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


def code_for(profile: str, name: str) -> str:
    """Stable for ever once written down."""
    row = store.one("SELECT code FROM agent_codes WHERE profile=?", (profile,))
    if row and row["code"]:
        return row["code"]
    taken = {r["code"] for r in store.query("SELECT code FROM agent_codes")}
    chosen = None
    for cand in _candidates(name or profile):
        if cand not in taken:
            chosen = cand
            break
    chosen = chosen or (name or profile)[:2].upper()
    store.execute(
        "INSERT OR REPLACE INTO agent_codes(profile, code, name, created_at) VALUES(?,?,?,?)",
        (profile, chosen, name or profile, time.time()),
    )
    return chosen


def code_of(profile: str) -> str | None:
    row = store.one("SELECT code FROM agent_codes WHERE profile=?", (profile,))
    return row["code"] if row else None


def name_of_code(code: str) -> str | None:
    row = store.one("SELECT name FROM agent_codes WHERE code=?", (code,))
    return row["name"] if row else None


def profile_of_code(code: str) -> str | None:
    row = store.one("SELECT profile FROM agent_codes WHERE code=?", (code,))
    return row["profile"] if row else None


def short_of(name: str) -> str:
    """The name without its noun, for a small card. Not a truncation."""
    words = [w for w in re.split(r"\s+", name.strip()) if w]
    if not words:
        return name
    nounish = {"agent", "assistant", "bot", "ai", "specialist", "the"}
    if len(words) > 1 and words[-1].lower() in nounish:
        return " ".join(words[:-1])
    return words[0] if len(words) > 1 else name


# ---------------------------------------------------------------------------
# state.db readers (read only, schema-tolerant)
# ---------------------------------------------------------------------------
def _open_ro(path: Path):
    try:
        uri = f"file:{path}?mode=ro"
        c = sqlite3.connect(uri, uri=True, timeout=5)
        c.row_factory = sqlite3.Row
        return c
    except sqlite3.Error:
        return None


def _tables(c) -> list[str]:
    return [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]


def _cols(c, table: str) -> list[str]:
    try:
        return [r[1] for r in c.execute(f"PRAGMA table_info({table})")]
    except sqlite3.Error:
        return []


def _pick(cols: list[str], *wanted: str) -> str | None:
    low = {c.lower(): c for c in cols}
    for w in wanted:
        if w in low:
            return low[w]
    for w in wanted:
        for c in cols:
            if w in c.lower():
                return c
    return None


def _state_stats(profile: str, since_24h: float, since_7d: float, month_start: float) -> dict:
    """Session/message stats for one seat. Empty dict when there is nothing to read."""
    db = _home(profile) / "state.db"
    if not db.exists():
        return {}
    c = _open_ro(db)
    if c is None:
        raise PermissionError("state.db not readable")
    try:
        tables = _tables(c)
        sessions_tbl = next((t for t in ("sessions", "session") if t in tables), None)
        msgs_tbl = next((t for t in ("messages", "turns", "message", "events") if t in tables), None)

        out = {"sessions_total": 0, "sessions_24h": 0, "last_active": None,
               "avg_response_s": None, "messages_7d": 0, "tokens_24h": 0,
               "hours_month": 0.0, "tokens_month": 0, "hourly_24h": {"you": [0] * 24, "agent": [0] * 24},
               "messages_24h": 0}

        if sessions_tbl:
            cols = _cols(c, sessions_tbl)
            tcol = _pick(cols, "updated_at", "last_active", "last_message_at", "modified_at", "created_at", "at")
            out["sessions_total"] = c.execute(f"SELECT COUNT(*) FROM {sessions_tbl}").fetchone()[0]
            if tcol:
                rows = c.execute(f"SELECT {tcol} AS t FROM {sessions_tbl}").fetchall()
                times = [float(r["t"]) for r in rows if r["t"] is not None]
                if times:
                    out["last_active"] = max(times)
                    out["sessions_24h"] = sum(1 for t in times if t >= since_24h)
                    out["hours_month"] = round(sum(1 for t in times if t >= month_start) * 0.25, 1)

        # response time: gaps between a user turn and the next agent turn
        if msgs_tbl:
            cols = _cols(c, msgs_tbl)
            tcol = _pick(cols, "at", "created_at", "timestamp", "time", "ts")
            rcol = _pick(cols, "role", "sender", "author", "kind", "type")
            tokcol = _pick(cols, "tokens", "total_tokens", "tokens_out", "completion_tokens")
            if tcol:
                gaps: list[float] = []
                if rcol:
                    rows = c.execute(
                        f"SELECT {tcol} AS t, {rcol} AS r FROM {msgs_tbl} ORDER BY {tcol}"
                    ).fetchall()
                    prev_user = None
                    for r in rows:
                        t = float(r["t"] or 0)
                        role = str(r["r"] or "").lower()
                        if role in ("user", "you", "human", "operator"):
                            prev_user = t
                            if t >= since_24h:
                                out["hourly_24h"]["you"][_hour(t)] += 1
                        elif prev_user is not None:
                            gaps.append(max(0.0, t - prev_user))
                            prev_user = None
                            if t >= since_24h:
                                out["hourly_24h"]["agent"][_hour(t)] += 1
                        if t >= since_7d:
                            out["messages_7d"] += 1
                        if t >= since_24h:
                            out["messages_24h"] += 1
                    if gaps:
                        out["avg_response_s"] = round(sum(gaps) / len(gaps), 1)
                if tokcol:
                    try:
                        row = c.execute(
                            f"SELECT COALESCE(SUM({tokcol}),0) AS a FROM {msgs_tbl} WHERE {tcol} >= ?",
                            (since_24h,),
                        ).fetchone()
                        out["tokens_24h"] = int(row["a"] or 0)
                        row = c.execute(
                            f"SELECT COALESCE(SUM({tokcol}),0) AS a FROM {msgs_tbl} WHERE {tcol} >= ?",
                            (month_start,),
                        ).fetchone()
                        out["tokens_month"] = int(row["a"] or 0)
                    except sqlite3.Error:
                        pass
        return out
    finally:
        c.close()


def _hour(ts: float) -> int:
    return int(datetime.fromtimestamp(ts).strftime("%H"))


# ---------------------------------------------------------------------------
# The board, the gateway
# ---------------------------------------------------------------------------
def _board_running_agents() -> set[str]:
    """Profiles with a card running and a heartbeat in the last 15 minutes."""
    db = HERMES / "kanban.db"
    if not db.exists():
        return set()
    c = _open_ro(db)
    if c is None:
        return set()
    try:
        tables = _tables(c)
        if "tasks" not in tables:
            return set()
        cols = _cols(c, "tasks")
        acol = _pick(cols, "assignee", "agent", "profile", "owner")
        scol = _pick(cols, "status", "state")
        if not (acol and scol):
            return set()
        hb_sql = "0"
        hcol = None
        if "task_runs" in tables:
            rcols = _cols(c, "task_runs")
            hcol = _pick(rcols, "heartbeat_at", "updated_at", "last_seen", "at")
        if hcol:
            hb_sql = (f"(SELECT MAX(r.{hcol}) FROM task_runs r "
                      f"WHERE r.task_id = t.id) ")
        q = (f"SELECT DISTINCT t.{acol} AS a FROM tasks t "
             f"WHERE t.{scol} IN ('running','claimed','in_progress') "
             f"AND {hb_sql} > ?")
        rows = c.execute(q, (time.time() - 900,)).fetchall()
        return {str(r["a"]) for r in rows if r["a"]}
    except sqlite3.Error:
        return set()
    finally:
        c.close()


def gateway() -> dict:
    """One gateway serves the whole install. gateway.pid is JSON, not a bare number."""
    state_p = HERMES / "gateway_state.json"
    pid_p = HERMES / "gateway.pid"
    info = {"up": False, "pid": None, "uptime_s": None, "kind": None}
    pid = None
    if pid_p.exists():
        try:
            raw = pid_p.read_text().strip()
            data = json.loads(raw)
            if isinstance(data, dict):
                pid = int(data.get("pid") or 0) or None
                info["kind"] = data.get("kind")
            else:
                pid = int(raw) or None
        except Exception:
            pid = None
    if state_p.exists():
        try:
            data = json.loads(state_p.read_text())
            pid = pid or int(data.get("pid") or 0) or None
            info["kind"] = info["kind"] or data.get("kind")
            started = data.get("started_at") or data.get("at")
            if started:
                info["uptime_s"] = round(time.time() - float(started), 1)
        except Exception:
            pass
    if pid:
        try:
            os.kill(pid, 0)
            info["up"] = True
        except OSError:
            info["up"] = False
    info["pid"] = pid
    return info


def cron_ticker() -> dict:
    hb = HERMES / "cron" / "ticker_heartbeat"
    if not hb.exists():
        return {"running": False, "heartbeat_s": None}
    try:
        age = time.time() - float(hb.read_text().strip())
    except Exception:
        return {"running": False, "heartbeat_s": None}
    return {"running": age < 300, "heartbeat_s": round(age, 1)}


# ---------------------------------------------------------------------------
# Build one agent record
# ---------------------------------------------------------------------------
def _status_for(profile: str, stats: dict, board_agents: set[str], readable: bool) -> str:
    if not readable:
        return "unreachable"
    if profile in board_agents:
        return "working"
    last = stats.get("last_active")
    if last and (time.time() - last) < 86400:
        return "active"
    return "ready"


def agents(force: bool = False) -> dict:
    now = time.time()
    if not force and _cache["value"] is not None and (now - _cache["at"]) < _CACHE_TTL:
        return _cache["value"]

    since_24h = now - 86400
    since_7d = now - 7 * 86400
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()

    board_agents = _board_running_agents()
    avatar_rows = {r["owner"]: r for r in store.query("SELECT * FROM avatars")}

    records: list[dict] = []
    for profile in profiles():
        home = _home(profile)
        readable = True
        try:
            stats = _state_stats(profile, since_24h, since_7d, month_start)
        except PermissionError:
            stats, readable = {}, False
        except Exception:
            stats, readable = {}, False

        name, _from_soul = name_from_soul(profile)
        name = _display_name(name)
        role = (role_from_soul(profile)
                or description_from_profile_yaml(profile)
                or f"One of the fleet's agents, running profile {profile}.")
        # A cloned profile carries the same SOUL name; the folder keeps them apart.
        if profile != "default" and name_from_soul(profile)[1]:
            for other in records:
                if other["name"] == name:
                    name = _titleise(profile)
                    break

        code = code_for(profile, name)
        status = _status_for(profile, stats, board_agents, readable)
        av = avatar_rows.get(code)
        avatar = None
        if av and av["kind"] == "upload" and av["file_name"]:
            avatar = {"id": av["file_name"], "url": f"/api/avatars/file?name={av['file_name']}",
                      "thumb": f"/api/avatars/file?name={av['file_name']}", "kind": "upload"}
        elif av and av["kind"] == "library" and av["library_id"]:
            avatar = {"id": av["library_id"], "url": "", "thumb": "", "kind": "library"}

        last_active = stats.get("last_active")
        records.append({
            "code": code,
            "short": short_of(name),
            "name": name,
            "role": role,
            "profile": profile,
            "model": model_from_config(profile) or "unknown",
            "status": status,
            "status_label": STATUS_LABELS[status],
            "present": True,
            "aliases": [code, short_of(name)],
            "building": f"{short_of(name)} {BUILDINGS.get(status, 'Cabin')}",
            "avatar": avatar,
            "portrait": av["library_id"] if (av and av["kind"] == "library") else (av["file_name"] if av else None),
            "last_active": last_active,
            "stats": {
                "last_active": last_active,
                "avg_response_s": stats.get("avg_response_s"),
                "sessions_24h": stats.get("sessions_24h", 0),
                "sessions_total": stats.get("sessions_total", 0),
                "messages_7d": stats.get("messages_7d", 0),
                "tokens_24h": stats.get("tokens_24h", 0),
                "hourly_24h": stats.get("hourly_24h", {"you": [0] * 24, "agent": [0] * 24}),
            },
        })

    # fleet roll-up
    hours = [0] * 24
    you = [0] * 24
    failed = [0] * 24
    for a in records:
        for i in range(24):
            you[i] += a["stats"]["hourly_24h"]["you"][i]
            hours[i] += a["stats"]["hourly_24h"]["agent"][i]

    fleet = {
        "seats": len(records),
        "working_now": sum(1 for a in records if a["status"] == "working"),
        "active_today": [a for a in records if a["status"] == "active" and a["stats"]["last_active"]],
        "avg_response_s": _avg([a["stats"]["avg_response_s"] for a in records]),
        "turns_24h": {"total": sum(hours), "failed": 0},
        "failed_24h": 0,
        "missions_total": _missions_total(),
        "handoffs_recent": _mission_handoffs(),
        "recent": _recent_sessions(),
        "messages_7d": sum(a["stats"]["messages_7d"] for a in records),
        "hours_month": round(sum(a["stats"].get("hours_month", 0) for a in records), 1),
        "tokens_month": sum(a["stats"].get("tokens_month", 0) for a in records),
        "sessions_24h": sum(a["stats"]["sessions_24h"] for a in records),
        "sessions_total": sum(a["stats"]["sessions_total"] for a in records),
        "hourly_24h": {"you": you, "agent": hours, "failed": failed},
        "heat": _heat(records),
        "heat_tz": store.settings().get("timezone", "UTC"),
        "links": _links(),
    }
    fleet["active_today"] = len(fleet["active_today"])

    value = {"agents": records, "fleet": fleet, "gateway": gateway(),
             "cron": cron_ticker(), "generated_at": now}
    _cache.update({"at": now, "value": value})
    return value


def _avg(values) -> float | None:
    nums = [v for v in values if v]
    return round(sum(nums) / len(nums), 1) if nums else None


def _missions_total() -> int:
    try:
        row = store.one("SELECT COUNT(*) AS n FROM missions WHERE cleared_at IS NULL")
        return int(row["n"]) if row else 0
    except Exception:
        return 0


def _mission_handoffs(limit: int = 8) -> list[dict]:
    """Recent step hand-offs, from our own mission tables."""
    try:
        rows = store.query(
            "SELECT s.agent AS to_code, m.id AS mission, s.title, s.status, s.started_at "
            "FROM mission_steps s JOIN missions m ON m.id = s.mission_id "
            "ORDER BY s.started_at DESC NULLS LAST LIMIT ?", (limit,),
        )
    except Exception:
        return []
    out = []
    for r in rows:
        to_code = r["to_code"] or ""
        out.append({"from": "EX" if to_code != "EX" else "OP", "to": to_code, "title": r["title"] or ""})
    return out


def _recent_sessions(limit: int = 12) -> list[dict]:
    """The session ticker. A dashboard chat is not a terminal, a plan is not a chat."""
    try:
        rows = store.query(
            "SELECT agent, source, conversation, MIN(at) AS started_at, COUNT(*) AS messages "
            "FROM turns GROUP BY agent, source, conversation ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
    except Exception:
        return []
    names = {r["code"]: r["name"] for r in store.query("SELECT code, name FROM agent_codes")}
    out = []
    for r in rows:
        conv = r["conversation"] or ""
        source = "mirai-mission" if conv.endswith("-mission") else "mirai"
        out.append({"code": r["agent"], "name": names.get(r["agent"], r["agent"]),
                    "source": source, "started_at": r["started_at"], "messages": r["messages"]})
    return out


def _heat(records: list[dict]) -> list[int]:
    """7 x 24 grid, agent turns per weekday-hour over the last week."""
    grid = [0] * (7 * 24)
    for a in records:
        for i, n in enumerate(a["stats"]["hourly_24h"]["agent"]):
            _ = i, n                          # today only; the grid fills from turns below
    try:
        rows = store.query("SELECT at, agent FROM turns WHERE role='agent' AND at >= ?",
                           (time.time() - 7 * 86400,))
        for r in rows:
            dt = datetime.fromtimestamp(r["at"])
            grid[dt.weekday() * 24 + dt.hour] += 1
    except Exception:
        pass
    return grid


def _links(limit: int = 24) -> list[dict]:
    """Who hands work to whom, counted from our mission steps."""
    try:
        rows = store.query(
            "SELECT agent AS to_code, COUNT(*) AS n FROM mission_steps GROUP BY agent ORDER BY n DESC LIMIT ?",
            (limit,),
        )
    except Exception:
        return []
    return [{"from": "EX", "to": r["to_code"], "count": r["n"]} for r in rows if r["to_code"]]


def invalidate() -> None:
    _cache["at"] = 0.0
