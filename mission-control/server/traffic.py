"""traffic.py — what the agents said to each other, read off the Hermes board.

READ ONLY. Nothing here creates a card: creating one makes an agent start
working within seconds, which costs money, and no dashboard route should be able
to do that by accident.

The trap this module exists around: the answer is NOT on the card. tasks.result
is empty on a real board; the worker's closing summary is task_runs.summary, a
second table, joined on the task id. That one sentence is most of this module.
"""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import store
from server import ApiError

HERMES = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
MAX_ROWS = 400


def _open_board():
    db = HERMES / "kanban.db"
    if not db.exists():
        raise ApiError(404, "no board on this machine (kanban.db not found)")
    try:
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        c.row_factory = sqlite3.Row
        return c
    except sqlite3.Error as e:
        raise ApiError(503, f"board not readable: {e}")


def _cols(c, table: str) -> list[str]:
    try:
        return [r[1] for r in c.execute(f"PRAGMA table_info({table})")]
    except sqlite3.Error:
        return []


def _pick(cols, *wanted):
    low = {c.lower(): c for c in cols}
    for w in wanted:
        if w in low:
            return low[w]
    for w in wanted:
        for c in cols:
            if w in c.lower():
                return c
    return None


MISSION_LINE = None  # compiled lazily


def traffic(req, query, body):              # noqa: ANN001
    import re
    global MISSION_LINE
    MISSION_LINE = MISSION_LINE or re.compile(r"\((NX-\d{4,6})\)")

    try:
        since = float(query.get("since") or 0) or None
    except ValueError:
        raise ApiError(400, "since must be a number")
    try:
        limit = min(MAX_ROWS, max(1, int(query.get("limit") or 120)))
    except ValueError:
        raise ApiError(400, "limit must be a number")
    wanted_mission = query.get("mission") or None

    c = _open_board()
    try:
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        if "tasks" not in tables:
            return {"exchanges": [], "count": 0, "note": "board has no tasks table"}
        tcols = _cols(c, "tasks")
        id_col = _pick(tcols, "id") or "id"
        title_col = _pick(tcols, "title", "name")
        body_col = _pick(tcols, "body", "description", "brief", "prompt")
        assignee_col = _pick(tcols, "assignee", "agent", "profile", "owner")
        status_col = _pick(tcols, "status", "state")
        parent_col = _pick(tcols, "parent", "parent_id", "waiting_on")
        created_col = _pick(tcols, "created_at", "at", "created")
        claimed_col = _pick(tcols, "claimed_at", "started_at")
        done_col = _pick(tcols, "done_at", "completed_at", "finished_at")

        run_cols = _cols(c, "task_runs") if "task_runs" in tables else []
        run_task = _pick(run_cols, "task_id", "task") if run_cols else None
        run_summary = _pick(run_cols, "summary", "result", "output") if run_cols else None
        run_error = _pick(run_cols, "error", "failure") if run_cols else None
        run_hb = _pick(run_cols, "heartbeat_at", "updated_at") if run_cols else None
        run_end = _pick(run_cols, "ended_at", "finished_at", "completed_at") if run_cols else None

        select = [f"t.{id_col} AS card"]
        for alias, col in (("title", title_col), ("brief", body_col), ("to", assignee_col),
                           ("status", status_col), ("created_at", created_col),
                           ("claimed_at", claimed_col), ("done_at", done_col)):
            select.append(f"t.{col} AS {alias}" if col else f"NULL AS {alias}")
        select.append(f"t.{parent_col} AS parent" if parent_col else "NULL AS parent")

        sql = f"SELECT {', '.join(select)} FROM tasks t"
        clauses, args = [], []
        if created_col and since:
            clauses.append(f"t.{created_col} >= ?")
            args.append(since)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += f" ORDER BY t.{created_col} ASC" if created_col else ""
        sql += f" LIMIT {limit * 3}"
        rows = c.execute(sql, args).fetchall()

        # waiting_on: codes of unfinished parents
        parent_status: dict[str, tuple[str, str]] = {}
        if parent_col and assignee_col:
            for r in rows:
                if r["card"]:
                    parent_status[str(r["card"])] = (str(r["to"] or ""), str(r["status"] or ""))

        summary_by_card: dict[str, dict] = {}
        if run_cols and run_task:
            for r in rows:
                try:
                    run = c.execute(
                        f"SELECT * FROM task_runs WHERE {run_task}=? ORDER BY rowid DESC LIMIT 1",
                        (r["card"],)).fetchone()
                except sqlite3.Error:
                    run = None
                if run is None:
                    continue
                summary_by_card[str(r["card"])] = {
                    "summary": (run[run_summary] if run_summary else None),
                    "error": (run[run_error] if run_error else None),
                    "ended_at": (run[run_end] if run_end else None),
                    "heartbeat_at": (run[run_hb] if run_hb else None),
                }

        import roster
        code_by_profile = {r["profile"]: r["code"] for r in store.query("SELECT profile, code FROM agent_codes")}

        exchanges = []
        for r in rows:
            brief = str(r["brief"] or "")
            m = MISSION_LINE.search(brief)
            mission = m.group(1) if m else None
            if wanted_mission and mission != wanted_mission:
                continue
            card_id = str(r["card"])
            run = summary_by_card.get(card_id)
            done = r["done_at"]
            # A stopped mission unassigns its cards: say "unassigned" rather than
            # printing question marks, and keep the card.
            assignee = str(r["to"] or "").strip() or "unassigned"
            to_code = code_by_profile.get(assignee, assignee.upper()[:2] if assignee != "unassigned" else "—")
            status = str(r["status"] or "")
            exchanges.append({
                "card": card_id,
                "from": "OP",
                "to": to_code,
                "title": r["title"],
                "brief": brief,
                "mission": mission,
                "sent_at": r["created_at"],
                "claimed_at": r["claimed_at"],
                "done_at": done,
                "heartbeat_at": (run or {}).get("heartbeat_at"),
                "status": status,
                "failed": status.lower() in ("failed", "error") or bool((run or {}).get("error")),
                "waiting_on": [],
                "reply": ({"summary": run.get("summary"), "error": run.get("error"),
                           "ended_at": run.get("ended_at")} if run and done else None),
            })
        exchanges = exchanges[-limit:]
        return {"exchanges": exchanges, "count": len(exchanges),
                "fetched_at": time.time(), "board": str(HERMES / "kanban.db")}
    finally:
        c.close()


def register(route, ApiError_):        # noqa: ANN001
    """Declare this module's routes. Called once by server.py at load time."""
    route("GET", "/api/traffic")(traffic)
