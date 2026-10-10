"""missions.py — what a mission is, how one is launched, and the seven verbs.

A mission moves through: planning, awaiting_approval, running, review, delivered.
It can also reach stopped or cancelled from any of those.

Two things in here are load bearing and silently wrong if missed:
  * the response key names (idx not ord, ts not at, time_limit_min) and the
    "limits" object, because the launch console fills its dropdowns from it and
    shows the template's own defaults for ever when the names are ignored;
  * the watcher thread that moves a mission from running to review. Nothing else
    in this build does it, and without it every approved mission stays running
    for ever.

Board integration goes through the hermes CLI. Where a board is not available
(MIRAI_KANBAN=off, or a hermes version without the kanban verbs), steps run
through chat.py instead and the mode is reported on every mission — see
_kanban_probe(). Nothing here pretends a card exists when it does not.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from datetime import datetime

import store
from server import ApiError

MIRAI_DIR = Path(os.environ.get("MIRAI_DIR", str(Path.home() / "mirai"))).expanduser()
DATA_DIR = Path(os.environ.get("MIRAI_DATA_DIR", str(MIRAI_DIR / "data"))).expanduser()
DOCS_DIR = DATA_DIR / "docs"

MISSION_ID_RE = re.compile(r"^NX-[0-9]{4,6}$")
ACTIONS = ("approve", "accept", "send_back", "replan", "stop", "cancel", "clear")
LIMITS = {"time": [15, 30, 60, 120, 240, 480], "steps": [2, 3, 4, 5, 6, 8]}
LENGTHS = ("short", "medium", "long")
LENGTH_WORDS = {"short": "about 150 words", "medium": "about 400 words", "long": "about 900 words"}

MAX_CARD_RETRIES = 3
WATCH_EVERY_S = 20

_SCHEMA = """
CREATE TABLE IF NOT EXISTS missions(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  objective TEXT NOT NULL,
  priority TEXT DEFAULT 'normal',
  deadline TEXT,
  status TEXT NOT NULL,
  length TEXT DEFAULT 'medium',
  review INTEGER DEFAULT 1,
  max_steps INTEGER DEFAULT 4,
  max_turns INTEGER DEFAULT 12,
  time_limit_min INTEGER DEFAULT 60,
  team TEXT,
  agents TEXT,
  created_at REAL NOT NULL,
  planned_at REAL, started_at REAL, ended_at REAL,
  completed_at REAL, delivered_at REAL, cleared_at REAL,
  result TEXT, error TEXT,
  mode TEXT
);
CREATE TABLE IF NOT EXISTS mission_steps(
  id INTEGER PRIMARY KEY,
  mission_id TEXT NOT NULL,
  idx INTEGER NOT NULL,
  title TEXT NOT NULL,
  agent TEXT,
  type TEXT DEFAULT 'work',
  status TEXT NOT NULL DEFAULT 'pending',
  needs TEXT,
  result TEXT,
  card_id TEXT,
  retries INTEGER DEFAULT 0,
  started_at REAL,
  completed_at REAL
);
CREATE TABLE IF NOT EXISTS mission_events(
  id INTEGER PRIMARY KEY,
  mission_id TEXT NOT NULL,
  ts REAL NOT NULL,
  kind TEXT NOT NULL,
  text TEXT NOT NULL
);
"""

store.ensure(_SCHEMA, "missions")

_watch_started = False
_watch_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _now() -> float:
    return time.time()


def _event(mission_id: str, kind: str, text: str) -> None:
    store.execute("INSERT INTO mission_events(mission_id, ts, kind, text) VALUES(?,?,?,?)",
                  (mission_id, _now(), kind, text))


def _audit(action: str, detail: dict) -> None:
    store.audit("operator", f"mission.{action}", detail)


def new_mission_id() -> str:
    """NX-1001 upward. Ids restart on a fresh install."""
    row = store.one("SELECT id FROM missions ORDER BY id DESC LIMIT 1")
    if not row:
        return "NX-1001"
    try:
        n = int(row["id"].split("-")[1])
    except Exception:
        return "NX-1001"
    return f"NX-{n + 1}"


def _hermes() -> str | None:
    for cand in ("/opt/homebrew/bin/hermes", "/usr/local/bin/hermes",
                 str(Path.home() / ".local" / "bin" / "hermes"), "/usr/bin/hermes"):
        if Path(cand).exists():
            return cand
    return shutil.which("hermes")


_kanban_state: dict = {"checked": 0.0, "ok": False, "detail": ""}


def _kanban_probe() -> bool:
    """Is a working board CLI available? Cached for five minutes."""
    if os.environ.get("MIRAI_KANBAN", "").lower() in ("off", "0", "false"):
        _kanban_state.update({"ok": False, "detail": "disabled by MIRAI_KANBAN=off"})
        return False
    if _kanban_state["checked"] and (_now() - _kanban_state["checked"]) < 300:
        return bool(_kanban_state["ok"])
    ok, detail = False, "hermes CLI not found"
    hx = _hermes()
    if hx:
        try:
            p = subprocess.run([hx, "kanban", "--help"], capture_output=True, text=True, timeout=20)
            ok = p.returncode == 0
            detail = "" if ok else (p.stderr or p.stdout or "").strip()[:200]
        except Exception as e:
            detail = str(e)[:200]
    _kanban_state.update({"checked": _now(), "ok": ok, "detail": detail})
    return ok


def _kanban(*args: str, timeout: int = 60) -> tuple[int, str, str]:
    hx = _hermes()
    if not hx:
        return 127, "", "hermes CLI not found"
    try:
        p = subprocess.run([hx, "kanban", *args], capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", "kanban command timed out"
    except OSError as e:
        return 126, "", str(e)


def mode() -> str:
    return "board" if _kanban_probe() else "local"


# ---------------------------------------------------------------------------
# Read side
# ---------------------------------------------------------------------------
def _mission_row(row: dict) -> dict:
    mission_id = row["id"]
    steps = store.query(
        "SELECT idx, title, agent, type, status, started_at, completed_at, result "
        "FROM mission_steps WHERE mission_id=? ORDER BY idx", (mission_id,))
    events = store.query(
        "SELECT ts, kind, text FROM mission_events WHERE mission_id=? ORDER BY id", (mission_id,))
    team = json.loads(row["team"] or "[]")
    agents = json.loads(row["agents"] or "[]")
    time_left = None
    if row["status"] == "running" and row["started_at"] and row["time_limit_min"]:
        time_left = max(0, int(row["started_at"] + row["time_limit_min"] * 60 - _now()))
    return {
        "id": mission_id,
        "name": row["name"],
        "objective": row["objective"],
        "status": row["status"],
        "priority": row["priority"],
        "length": row["length"],
        "created_at": row["created_at"],
        "planned_at": row["planned_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "delivered_at": row["delivered_at"],
        "cleared_at": row["cleared_at"],
        "result": row["result"],
        "error": row["error"],
        "max_steps": row["max_steps"],
        "max_turns": row["max_turns"],
        "time_limit_min": row["time_limit_min"],
        "time_left_s": time_left,
        "review": bool(row["review"]),
        "mode": row["mode"] or mode(),
        "team": team,
        "agents": agents,
        "steps": [dict(s) for s in steps],
        "events": [dict(e) for e in events],
    }


def list_missions(req, query, body):        # noqa: ANN001
    include_cleared = str(query.get("all", "0")).lower() in ("1", "true", "yes")
    sql = ("SELECT * FROM missions " + ("" if include_cleared else "WHERE cleared_at IS NULL ") +
           "ORDER BY created_at DESC")
    rows = store.query(sql)
    return {"missions": [_mission_row(r) for r in rows], "limits": LIMITS, "mode": mode()}


# ---------------------------------------------------------------------------
# Launching (prompt 22)
# ---------------------------------------------------------------------------
def create_mission(req, query, body):       # noqa: ANN001
    if body is None:
        body = {}
    name = str(body.get("name") or "").strip()
    objective = str(body.get("objective") or "").strip()
    if not name:
        raise ApiError(400, "name is required")
    if not objective:
        raise ApiError(400, "objective is required")

    length = str(body.get("length") or "medium").lower()
    if length not in LENGTHS:
        raise ApiError(400, f"length must be one of: {', '.join(LENGTHS)}")

    try:
        max_steps = max(1, min(12, int(body.get("max_steps") or 4)))
    except (TypeError, ValueError):
        raise ApiError(400, "max_steps must be a number")
    try:
        time_limit_min = max(5, min(1440, int(body.get("time_limit_min") or 60)))
    except (TypeError, ValueError):
        raise ApiError(400, "time_limit_min must be a number")

    agents = body.get("agents") or []
    if not isinstance(agents, list):
        raise ApiError(400, "agents must be a list of agent codes")

    mission_id = new_mission_id()
    store.execute(
        "INSERT INTO missions(id, name, objective, priority, deadline, status, length, review, "
        "max_steps, time_limit_min, agents, team, created_at, mode) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (mission_id, name, objective, str(body.get("priority") or "normal"),
         body.get("deadline"), "planning", length,
         1 if body.get("review", True) else 0, max_steps, time_limit_min,
         json.dumps(agents), "[]", _now(), mode()),
    )
    _event(mission_id, "created", f"Mission created: {name}")
    _audit("create", {"id": mission_id, "name": name})
    threading.Thread(target=_plan, args=(mission_id,), daemon=True).start()
    return {"id": mission_id, "status": "planning", "mode": mode()}


def _planner_profile() -> str:
    """The default profile: no fresh Hermes crew has a seat called Executor."""
    import roster
    profs = roster.profiles()
    return "default" if "default" in profs else (profs[0] if profs else "default")


def _ask_planner(prompt: str) -> str:
    """One planning turn through chat.py, in the mission's own conversation."""
    import chat
    profile = _planner_profile()
    code = None
    try:
        import roster
        for a in roster.agents().get("agents", []):
            if a["profile"] == profile:
                code = a["code"]
                break
    except Exception:
        pass
    # The planner runs in a conversation of its own: a plan is not a chat.
    return chat._send_turn(code or "EX", prompt, [])


def _plan(mission_id: str) -> None:
    row = store.one("SELECT * FROM missions WHERE id=?", (mission_id,))
    if not row:
        return
    import roster
    seats = [{"code": a["code"], "name": a["name"], "profile": a["profile"]}
             for a in roster.agents().get("agents", [])]
    wanted = json.loads(row["agents"] or "[]")
    if wanted:
        seats = [s for s in seats if s["code"] in wanted] or seats

    prompt = (
        "You are planning a mission for the operator. Turn this objective into steps.\n"
        f"Objective: {row['objective']}\n"
        f"Maximum steps: {row['max_steps']}.\n"
        "Answer with JSON only: a list of objects {agent, title, needs} where agent is one of "
        "these codes: " + ", ".join(f"{s['code']} ({s['name']})" for s in seats) + ". "
        "needs holds the zero based indexes of the steps this one waits on ([] when it can start now). "
        "No prose, no code fences."
    )

    plan = None
    note = ""
    try:
        raw = _ask_planner(prompt)
        plan = _parse_plan(raw, seats, row["max_steps"])
        if plan is None:
            note = "the plan could not be read; falling back to a single step"
    except Exception as e:
        note = f"planning failed ({e}); falling back to a single step"

    if plan is None:
        first = wanted[0] if wanted else (seats[0]["code"] if seats else "EX")
        plan = [{"agent": first, "title": row["objective"], "needs": []}]

    # Only assign a step to a seat that can actually answer: a profile without a
    # login would take the card and die on it all night.
    answerable = {s["code"] for s in seats}
    cleaned = []
    for i, step in enumerate(plan[: row["max_steps"]]):
        agent = step.get("agent") if step.get("agent") in answerable else (seats[0]["code"] if seats else "EX")
        cleaned.append({"agent": agent, "title": str(step.get("title") or f"Step {i+1}")[:300],
                        "needs": [n for n in (step.get("needs") or []) if isinstance(n, int) and 0 <= n < i]})

    with store.con() as c:  # noqa: SIM117 — one transaction for the whole step list
        store.execute("DELETE FROM mission_steps WHERE mission_id=?", (mission_id,))
        for i, step in enumerate(cleaned):
            store.execute(
                "INSERT INTO mission_steps(mission_id, idx, title, agent, type, status, needs) "
                "VALUES(?,?,?,?,?,?,?)",
                (mission_id, i, step["title"], step["agent"], "work", "pending", json.dumps(step["needs"])))

    store.execute("UPDATE missions SET status='awaiting_approval', planned_at=?, team=?, error=? WHERE id=?",
                  (_now(), json.dumps(sorted({s["agent"] for s in cleaned})), note or None, mission_id))
    _event(mission_id, "planned", f"Plan ready: {len(cleaned)} steps" + (f". Note: {note}" if note else ""))
    if note:
        _event(mission_id, "warning", note)


def _parse_plan(raw: str, seats: list[dict], max_steps: int):
    """Defensive: strip fences, find the JSON, validate codes and step count."""
    if not raw:
        return None
    text = raw.strip()
    text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text, flags=re.M).strip()
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except Exception:
        return None
    if not isinstance(data, list) or not data:
        return None
    codes = {s["code"] for s in seats}
    out = []
    for item in data:
        if not isinstance(item, dict):
            return None
        agent = item.get("agent")
        if agent not in codes:
            return None
        out.append({"agent": agent, "title": item.get("title") or "Untitled step",
                    "needs": item.get("needs") or []})
    if len(out) > max_steps:
        return None
    return out


# ---------------------------------------------------------------------------
# A card per step (prompt 23)
# ---------------------------------------------------------------------------
def _chain_length(steps: list[dict]) -> int:
    """The longest chain of steps that wait on one another, for the time share."""
    depth = {}
    for step in steps:
        needs = step.get("needs") or []
        depth[step["idx"]] = 1 + max([depth.get(n, 1) for n in needs] or [0])
    return max(depth.values() or [1])


def _brief(mission: dict, step: dict, per_step_min: int) -> str:
    """The instruction an agent gets. It says where to write and how long it has."""
    wc = LENGTH_WORDS.get(mission["length"], LENGTH_WORDS["medium"])
    return (
        f"You are working a step of the operator's mission \"{mission['name']}\" ({mission['id']}).\n\n"
        f"Mission objective: {mission['objective']}\n"
        f"Your step: {step['title']}\n\n"
        f"Write your work as deliverable.md in your workspace, to {wc}. "
        "Close with one paragraph that ends with the full path of that file.\n\n"
        f"Time: the whole mission has {mission['time_limit_min']} minutes from approval, "
        f"and this step's share of it is about {per_step_min} minutes. Stay inside it.\n\n"
        "Facts only; say when something is uncertain. Do not send, publish, buy or delete anything."
    )


def _create_card(mission: dict, step: dict, per_step_min: int) -> str | None:
    """One board card waiting on the cards it needs, so results flow down."""
    if mode() == "local":
        return None
    import roster
    profile = roster.profile_of_code(step["agent"] or "") or "default"
    args = ["add", "--title", f"{mission['id']} step {step['idx'] + 1}: {step['title']}",
            "--assignee", profile, "--body", _brief(mission, step, per_step_min),
            "--max-runtime-min", str(per_step_min)]
    parents = []
    for n in (step.get("needs") or []):
        peer = store.one("SELECT card_id FROM mission_steps WHERE mission_id=? AND idx=?",
                         (mission["id"], n))
        if peer and peer["card_id"]:
            parents.append(peer["card_id"])
    for p in parents:
        args += ["--parent", p]
    rc, out, err = _kanban(*args)
    if rc != 0:
        return None
    m = re.search(r"\b(t_[A-Za-z0-9]+)\b", out)
    return m.group(1) if m else (out.strip().split()[-1] if out.strip() else None)


def _start_local_runner(mission_id: str) -> None:
    """No board available: run the steps through chat.py, one after another."""
    def run() -> None:
        mission = store.one("SELECT * FROM missions WHERE id=?", (mission_id,))
        if not mission:
            return
        steps = store.query("SELECT * FROM mission_steps WHERE mission_id=? ORDER BY idx", (mission_id,))
        per_step = max(1, int((mission["time_limit_min"] or 60) / max(1, _chain_length([
            {"idx": s["idx"], "needs": json.loads(s["needs"] or "[]")} for s in steps]))))
        import chat
        for s in steps:
            row = store.one("SELECT status FROM missions WHERE id=?", (mission_id,))
            if not row or row["status"] not in ("running",):
                return
            store.execute("UPDATE mission_steps SET status='running', started_at=? WHERE id=?",
                          (_now(), s["id"]))
            _event(mission_id, "step", f"Step {s['idx'] + 1} started with {s['agent']}")
            try:
                reply = chat._send_turn(s["agent"], _brief(mission, s, per_step), [])
                store.execute("UPDATE mission_steps SET status='done', completed_at=?, result=? WHERE id=?",
                              (_now(), reply, s["id"]))
                _event(mission_id, "step", f"Step {s['idx'] + 1} done")
            except Exception as e:
                store.execute("UPDATE mission_steps SET status='failed', completed_at=? WHERE id=?",
                              (_now(), s["id"]))
                _event(mission_id, "step", f"Step {s['idx'] + 1} failed: {e}")
        _finish_if_complete(mission_id)

    threading.Thread(target=run, daemon=True).start()


# ---------------------------------------------------------------------------
# The seven verbs
# ---------------------------------------------------------------------------
def action(req, query, body):               # noqa: ANN001
    if body is None:
        body = {}
    mission_id = str(body.get("id") or "").strip()
    act = str(body.get("action") or "").strip().lower()
    note = str(body.get("note") or "").strip()

    if act not in ACTIONS:
        raise ApiError(400, f"action must be one of: {', '.join(ACTIONS)}")
    if not MISSION_ID_RE.match(mission_id):
        raise ApiError(400, "id must look like NX-1001")

    row = store.one("SELECT * FROM missions WHERE id=?", (mission_id,))
    if not row:
        raise ApiError(404, f"no mission {mission_id}")

    handlers = {
        "approve": _approve, "accept": _accept, "send_back": _send_back,
        "replan": _replan, "stop": _stop, "cancel": _cancel, "clear": _clear,
    }
    result = handlers[act](row, note)
    _audit(act, {"id": mission_id, "note": note or None})
    return {"id": mission_id, "action": act, **result,
            "mission": _mission_row(store.one("SELECT * FROM missions WHERE id=?", (mission_id,)))}


def _approve(row: dict, note: str) -> dict:
    if row["status"] != "awaiting_approval":
        raise ApiError(409, f"approve needs a mission awaiting approval, this one is {row['status']}")
    mission_id = row["id"]
    steps = store.query("SELECT * FROM mission_steps WHERE mission_id=? ORDER BY idx", (mission_id,))
    if not steps:
        raise ApiError(409, "this mission has no steps to run")

    chain = _chain_length([{"idx": s["idx"], "needs": json.loads(s["needs"] or "[]")} for s in steps])
    per_step = max(1, int((row["time_limit_min"] or 60) / max(1, chain)))

    placed, failed = 0, []
    for s in steps:
        card = _create_card(row, s, per_step)
        if card:
            store.execute("UPDATE mission_steps SET card_id=? WHERE id=?", (card, s["id"]))
            placed += 1
        elif mode() == "board":
            # A step whose card could not be created has no card to watch: mark it
            # failed at approval time rather than waiting on it for ever.
            failed.append(s["idx"])
            store.execute("UPDATE mission_steps SET status='failed', completed_at=? WHERE id=?",
                          (_now(), s["id"]))
            _event(mission_id, "error", f"Step {s['idx'] + 1} could not be placed on the board")

    store.execute("UPDATE missions SET status='running', started_at=? WHERE id=?", (_now(), mission_id))
    _event(mission_id, "approved", f"Approved by the operator; {placed} card(s) placed"
                                   + (f", {len(failed)} could not be placed" if failed else ""))

    if mode() == "local":
        _event(mission_id, "note", "No board available — steps run through chat, one at a time")
        _start_local_runner(mission_id)
    else:
        _ensure_watcher()
    return {"cards": placed, "failed_steps": failed, "mode": mode()}


def _accept(row: dict, note: str) -> dict:
    if row["status"] != "review":
        raise ApiError(409, f"accept needs a mission in review, this one is {row['status']}")
    store.execute("UPDATE missions SET status='delivered', delivered_at=?, completed_at=COALESCE(completed_at, ?) WHERE id=?",
                  (_now(), _now(), row["id"]))
    _event(row["id"], "delivered", "Delivered to the operator")
    _file_result(row["id"], "Delivered")
    return {}


def _send_back(row: dict, note: str) -> dict:
    if row["status"] != "review":
        raise ApiError(409, f"send_back needs a mission in review, this one is {row['status']}")
    if not note:
        raise ApiError(400, "send_back needs a note saying what to change")
    mission_id = row["id"]
    nxt = store.one("SELECT COALESCE(MAX(idx), -1) AS m FROM mission_steps WHERE mission_id=?",
                    (mission_id,))["m"] + 1
    first_agent = store.one("SELECT agent FROM mission_steps WHERE mission_id=? ORDER BY idx LIMIT 1",
                            (mission_id,))
    store.execute(
        "INSERT INTO mission_steps(mission_id, idx, title, agent, type, status, needs) VALUES(?,?,?,?,?,?,?)",
        (mission_id, nxt, f"Revision: {note[:180]}", (first_agent or {}).get("agent") or "EX",
         "revision", "pending", json.dumps([])))
    store.execute("UPDATE missions SET status='running' WHERE id=?", (mission_id,))
    _event(mission_id, "revision", f"Sent back with a note: {note}")
    if mode() == "local":
        _start_local_runner(mission_id)
    return {"step": nxt}


def _replan(row: dict, note: str) -> dict:
    mission_id = row["id"]
    if _kanban_probe():
        for s in store.query("SELECT card_id FROM mission_steps WHERE mission_id=? AND card_id IS NOT NULL",
                             (mission_id,)):
            _stop_card(s["card_id"])
    store.execute("DELETE FROM mission_steps WHERE mission_id=?", (mission_id,))
    store.execute("UPDATE missions SET status='planning', started_at=NULL, error=NULL WHERE id=?", (mission_id,))
    _event(mission_id, "replan", "Replanning: old steps discarded")
    threading.Thread(target=_plan, args=(mission_id,), daemon=True).start()
    return {}


def _stop_card(card_id: str) -> None:
    """IN THIS ORDER: reclaim (kills the worker), assign none, archive.

    Assigning none to a card that is still running is silently ignored, and
    reclaim alone does not unassign, so the other order leaves the card archived
    and still owned by an agent.
    """
    if mode() == "local" or not card_id:
        return
    _kanban("reclaim", card_id)
    _kanban("assign", card_id, "--none")
    _kanban("archive", card_id)


def _halt(row: dict, status: str, note: str, why: str) -> dict:
    mission_id = row["id"]
    for s in store.query("SELECT card_id FROM mission_steps WHERE mission_id=? AND card_id IS NOT NULL "
                         "AND status IN ('pending','running')", (mission_id,)):
        _stop_card(s["card_id"])
    store.execute("UPDATE missions SET status=?, ended_at=?, error=COALESCE(?, error) WHERE id=?",
                  (status, _now(), note or None, mission_id))
    _event(mission_id, status, why)
    return {}


def _stop(row: dict, note: str) -> dict:
    return _halt(row, "stopped", note, "Stopped" + (f": {note}" if note else ""))


def _cancel(row: dict, note: str) -> dict:
    return _halt(row, "cancelled", note, "Cancelled by the operator" + (f": {note}" if note else ""))


def _clear(row: dict, note: str) -> dict:
    if row["status"] not in ("delivered", "cancelled", "stopped"):
        raise ApiError(409, f"clear needs a delivered, cancelled or stopped mission, this one is {row['status']}")
    # The row, its steps and its events stay: only the board presence changes.
    store.execute("UPDATE missions SET cleared_at=? WHERE id=?", (_now(), row["id"]))
    _event(row["id"], "cleared", "Cleared from the board (the document is untouched)")
    return {}


def clear_many(req, query, body):           # noqa: ANN001
    if body is None:
        body = {}
    ids = body.get("ids")
    if not isinstance(ids, list) or not ids:
        raise ApiError(400, "ids must be a non-empty list")
    cleared = 0
    for mid in ids:
        mid = str(mid)
        if not MISSION_ID_RE.match(mid):
            raise ApiError(400, f"bad mission id: {mid}")
        row = store.one("SELECT * FROM missions WHERE id=?", (mid,))
        if row and row["status"] in ("delivered", "cancelled", "stopped"):
            _clear(row, "")
            cleared += 1
    _audit("clear_many", {"ids": ids, "cleared": cleared})
    return {"cleared": cleared}


# ---------------------------------------------------------------------------
# The watcher: something HAS to move a mission from running to review
# ---------------------------------------------------------------------------
def _ensure_watcher() -> None:
    global _watch_started
    with _watch_lock:
        if _watch_started:
            return
        _watch_started = True
        threading.Thread(target=_watch_loop, daemon=True).start()


def _watch_loop() -> None:
    while True:
        try:
            _watch_once()
        except Exception:
            pass
        time.sleep(WATCH_EVERY_S)


def _watch_once() -> None:
    missions = store.query("SELECT * FROM missions WHERE status='running'")
    for m in missions:
        if m["mode"] == "local" or mode() == "local":
            continue
        if m["started_at"] and m["time_limit_min"] and _now() > m["started_at"] + m["time_limit_min"] * 60:
            _halt(m, "stopped", "", "Time limit reached — stopped by the same code path as a manual stop")
            continue
        _sync_mission_from_board(m)
    for m in store.query("SELECT * FROM missions WHERE status='running'"):
        _finish_if_complete(m["id"])


def _sync_mission_from_board(m: dict) -> None:
    """Join tasks to task_runs, copy the worker's summary onto its step and read
    the document it wrote (deliverable.md, else the largest .md) onto the step too."""
    db = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))) / "kanban.db"
    if not db.exists():
        return
    import sqlite3
    try:
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        c.row_factory = sqlite3.Row
    except sqlite3.Error:
        return
    try:
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        if "tasks" not in tables:
            return
        for step in store.query("SELECT * FROM mission_steps WHERE mission_id=? AND card_id IS NOT NULL",
                                (m["id"],)):
            if step["status"] in ("done", "failed") and step["result"]:
                continue
            try:
                row = c.execute(
                    "SELECT t.*, (SELECT summary FROM task_runs r WHERE r.task_id=t.id "
                    "ORDER BY r.id DESC LIMIT 1) AS run_summary "
                    "FROM tasks t WHERE t.id=?", (step["card_id"],)).fetchone()
            except sqlite3.Error:
                continue
            if row is None:
                continue
            state = str(row["status"] or "").lower()
            started = row["started_at"] if "started_at" in row.keys() else None
            if state in ("running", "in_progress") or started:
                if step["status"] == "pending":
                    store.execute("UPDATE mission_steps SET status='running', started_at=COALESCE(?, ?) WHERE id=?",
                                  (started, _now(), step["id"]))
            if state in ("done", "completed", "failed", "cancelled"):
                summary = (row["run_summary"] or "").strip() if "run_summary" in row.keys() else ""
                doc = _find_deliverable(row["id"] if "id" in row.keys() else step["card_id"])
                result = summary or (f"Document: {doc}" if doc else "")
                new_status = "done" if state in ("done", "completed") else "failed"
                store.execute(
                    "UPDATE mission_steps SET status=?, completed_at=?, result=COALESCE(result, ?) WHERE id=?",
                    (new_status, _now(), result, step["id"]))
                _event(m["id"], "step", f"Step {step['idx'] + 1} {new_status}")
            elif state == "ready" and step["status"] == "running":
                # The dispatcher requeued a crashed card: still open, but capped.
                if (step["retries"] or 0) >= MAX_CARD_RETRIES:
                    store.execute("UPDATE mission_steps SET status='failed', completed_at=? WHERE id=?",
                                  (_now(), step["id"]))
                    _halt(m, "stopped", "", f"Step {step['idx'] + 1} was requeued more than "
                                            f"{MAX_CARD_RETRIES} times — mission stopped")
                else:
                    store.execute("UPDATE mission_steps SET retries=retries+1 WHERE id=?", (step["id"],))
    finally:
        c.close()


def _find_deliverable(card_id: str) -> str | None:
    """deliverable.md, else the largest .md, in the card's workspace OR under
    kanban/attachments/<card>, where Hermes moves a finished card's folder."""
    hermes = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
    candidates = []
    for base in (hermes / "kanban" / "workspaces", hermes / "kanban" / "attachments"):
        if not base.exists():
            continue
        hits = [p for p in base.rglob(f"*{card_id}*") if p.is_dir()] or []
        for h in hits:
            d = h / "deliverable.md"
            if d.exists():
                candidates.append(d)
            else:
                mds = sorted(h.glob("*.md"), key=lambda p: p.stat().st_size, reverse=True)
                candidates.extend(mds[:1])
    if not candidates:
        return None
    best = max(candidates, key=lambda p: p.stat().st_size)
    try:
        return str(best)
    except Exception:
        return None


def _finish_if_complete(mission_id: str) -> None:
    m = store.one("SELECT * FROM missions WHERE id=?", (mission_id,))
    if not m or m["status"] != "running":
        return
    steps = store.query("SELECT * FROM mission_steps WHERE mission_id=?", (mission_id,))
    open_steps = [s for s in steps if s["status"] in ("pending", "running")]
    if open_steps:
        return
    result = _compose_result(mission_id)
    target = "review" if m["review"] else "delivered"
    store.execute(
        "UPDATE missions SET status=?, completed_at=?, delivered_at=? , result=? WHERE id=?",
        (target, _now(), _now() if target == "delivered" else None, result, mission_id))
    _event(mission_id, target, "All steps finished — mission moved to " + target)
    _file_result(mission_id, "In review" if target == "review" else "Delivered")


def _compose_result(mission_id: str) -> str:
    """A summary numbered by agent, then one section per step with its document.

    Written the way the Docs reader reads: a blank line around every heading and
    list item, no bold markers, no em dashes.
    """
    m = store.one("SELECT * FROM missions WHERE id=?", (mission_id,))
    steps = store.query("SELECT * FROM mission_steps WHERE mission_id=? ORDER BY idx", (mission_id,))
    import roster
    names = {r["code"]: r["name"] for r in store.query("SELECT code, name FROM agent_codes")}

    by_agent: dict[str, list[str]] = {}
    for s in steps:
        by_agent.setdefault(s["agent"] or "—", []).append(f"{s['title']} ({s['status']})")

    lines = [f"# {m['name']}", "", f"Mission {m['id']} — {m['status']}", "",
             "## Summary", ""]
    for code, items in by_agent.items():
        lines.append(f"- {names.get(code, code)} ({code}):")
        for it in items:
            lines.append(f"  - {it}")
    lines.append("")
    for s in steps:
        lines += [f"## Step {s['idx'] + 1}: {s['title']}", "",
                  f"Agent: {names.get(s['agent'] or '', s['agent'] or 'unassigned')}", ""]
        if s["result"]:
            lines += [s["result"], ""]
        else:
            lines += ["This step wrote nothing.", ""]
    return "\n".join(lines).strip() + "\n"


def _file_result(mission_id: str, status_label: str) -> None:
    """One document per mission, rewritten on a revision, never duplicated."""
    m = store.one("SELECT * FROM missions WHERE id=?", (mission_id,))
    if not m:
        return
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", m["name"].lower()).strip("-")[:60] or "mission"
    date = datetime.now().strftime("%Y-%m-%d")
    folder = DOCS_DIR / "EX"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{date}_{slug}.md"
    existing = None
    for p in folder.glob(f"*_{slug}.md"):
        if f"mission: {mission_id}" in p.read_text(encoding="utf-8", errors="replace")[:600]:
            existing = p
            break
    target = existing or path
    created = target.stat().st_ctime if target.exists() else _now()
    front = (f"---\ntitle: {m['name']}\nagent: EX\nmission: {mission_id}\n"
             f"status: {status_label}\ncreated: {datetime.fromtimestamp(created).strftime('%Y-%m-%d')}\n"
             f"updated: {datetime.now().strftime('%Y-%m-%d')}\n---\n\n")
    target.write_text(front + (m["result"] or ""), encoding="utf-8")


def register(route, ApiError_):        # noqa: ANN001
    """Declare this module's routes. Called once by server.py at load time."""
    route("GET", "/api/missions")(list_missions)
    route("POST", "/api/missions")(create_mission)
    route("POST", "/api/missions/action")(action)
    route("POST", "/api/missions/clear")(clear_many)
