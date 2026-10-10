"""cron.py — standing orders: the jobs each agent keeps on a schedule.

Each profile keeps its jobs at <profile home>/cron/jobs.json. That file is an
OBJECT with a "jobs" key, not a bare list. A missing or half written file is an
empty list, never an exception — on a fresh install no profile has one at all,
and an empty Schedule page is the correct first sight of this feature.

Two things that bite if they are missed:
  * `live` is a boolean and the page counts it: without it the page announces
    "LIVE 0 of 6 held" over six jobs that are all running.
  * the expression is nested (schedule.expr with schedule.kind and
    schedule.display beside it), not a bare string.

For CRON the CLI verb is remove; for PROFILES it is delete. Cron accepts remove,
rm and delete alike, so a wrong guess does not fail at the command — it fails
later, somewhere else.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import store
from server import ApiError

HERMES = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
ACTIONS = {"run": "run", "pause": "pause", "resume": "resume", "delete": "remove"}

DOW = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
MON = ["", "January", "February", "March", "April", "May", "June", "July",
       "August", "September", "October", "November", "December"]


def _hermes() -> str:
    for cand in ("/opt/homebrew/bin/hermes", "/usr/local/bin/hermes",
                 str(Path.home() / ".local" / "bin" / "hermes"), "/usr/bin/hermes"):
        if Path(cand).exists():
            return cand
    found = shutil.which("hermes")
    if not found:
        raise ApiError(503, "hermes CLI not found")
    return found


def _seats() -> dict[str, str]:
    """profile name -> display name, for tagging every job with its owner."""
    import roster
    return {a["profile"]: a["name"] for a in roster.agents()["agents"]}


def _english(expr: str) -> str:
    """The expression as a sentence. Handed back as written whenever it cannot be
    read confidently — a wrong sentence about when a job fires is worse than the
    raw form."""
    try:
        parts = expr.split()
        if len(parts) != 5:
            return expr
        minute, hour, dom, month, dow = parts

        def num(x: str) -> int | None:
            return int(x) if x.isdigit() else None

        time_bit = ""
        if minute.isdigit() and hour.isdigit():
            time_bit = f"at {int(hour):02d}:{int(minute):02d}"
        elif hour.isdigit() and minute == "*":
            time_bit = f"every minute of {int(hour):02d}:00–{int(hour):02d}:59"
        elif hour == "*" and minute == "*":
            time_bit = "every minute"

        if dom == "*" and month == "*" and dow == "*":
            if time_bit == "every minute":
                return "Every minute"
            if time_bit:
                return f"Every day {time_bit}"
        if dom.isdigit() and month == "*" and dow == "*" and time_bit:
            return f"Every month on day {int(dom)} {time_bit}"
        if dow.isdigit() and dom == "*" and month == "*" and time_bit:
            return f"Every {DOW[int(dow) % 7]} {time_bit}"
        if dom == "*" and month.isdigit() and dow == "*" and time_bit:
            return f"Every day in {MON[int(month) % 13] if month.isdigit() else month} {time_bit}"
        if minute.startswith("*/") and hour == "*" and dom == "*" and month == "*" and dow == "*":
            return f"Every {minute[2:]} minutes"
        if hour.startswith("*/") and dom == "*" and month == "*" and dow == "*" and minute.isdigit():
            return f"Every {hour[2:]} hours at minute {int(minute):02d}"
        return expr
    except Exception:
        return expr


def _jobs_for(profile: str, display_name: str) -> list[dict]:
    path = (HERMES if profile == "default" else HERMES / "profiles" / profile) / "cron" / "jobs.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    raw_jobs = data.get("jobs") if isinstance(data, dict) else data
    if isinstance(raw_jobs, dict):
        # Some Hermes builds key the jobs by id instead of listing them. Both are
        # the same file, so both are read: a map is turned into a list here and
        # the key becomes the id when the job does not carry one.
        raw_jobs = [({**v, "id": v.get("id") or k} if isinstance(v, dict) else v)
                    for k, v in raw_jobs.items()]
    if not isinstance(raw_jobs, list):
        return []
    out = []
    for job in raw_jobs:
        if not isinstance(job, dict):
            continue
        sched = job.get("schedule") or {}
        expr = sched.get("expr") if isinstance(sched, dict) else str(sched)
        last_status = job.get("last_status") or job.get("last_result")
        out.append({
            "id": str(job.get("id") or job.get("name") or ""),
            "name": job.get("name") or job.get("id") or "(unnamed job)",
            "agent": profile,
            "agent_name": display_name,
            "model": job.get("model") or "",
            "expr": expr or "",
            "english": _english(expr or "") if expr else "",
            "live": bool(job.get("live", job.get("enabled", not job.get("paused", False)))),
            "next_run_at": job.get("next_run_at"),
            "last_run_at": job.get("last_run_at"),
            "last_status": last_status,
            "last_error": job.get("last_error"),
            "runs": job.get("runs") or job.get("run_count") or 0,
            "deliver": job.get("deliver") or job.get("channel") or "",
            "paused_reason": job.get("paused_reason"),
            "prompt": job.get("prompt") or job.get("instructions") or "",
        })
    return out


def _ticker() -> dict:
    import roster
    return roster.cron_ticker()


def list_jobs(req, query, body):            # noqa: ANN001
    seats = _seats()
    jobs: list[dict] = []
    for profile, display in seats.items():
        jobs.extend(_jobs_for(profile, display))
    return {"jobs": jobs, "scheduler": _ticker(), "seats": len(seats)}


def action(req, query, body):               # noqa: ANN001
    if body is None:
        body = {}
    agent = str(body.get("agent") or "").strip()
    job_id = str(body.get("id") or "").strip()
    act = str(body.get("action") or "").strip().lower()

    # Guarded four ways, in this order.
    if act not in ACTIONS:
        raise ApiError(400, f"action must be one of: {', '.join(ACTIONS)}")
    if not JOB_ID_RE.match(job_id):
        raise ApiError(400, "job id has unexpected characters")
    seats = _seats()
    if agent not in seats:
        raise ApiError(404, f"no seat called {agent}")
    jobs = _jobs_for(agent, seats[agent])
    if not any(j["id"] == job_id or j["name"] == job_id for j in jobs):
        raise ApiError(404, f"no job {job_id} on {agent}")

    cmd = [_hermes()]
    if agent != "default":
        cmd += ["-p", agent]
    cmd += ["cron", ACTIONS[act], job_id]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise ApiError(504, "the cron command timed out")
    if p.returncode != 0:
        raise ApiError(500, f"hermes cron {ACTIONS[act]} failed: {(p.stderr or p.stdout).strip()[:300]}")

    store.audit("operator", "cron.action", {"agent": agent, "id": job_id, "action": act})

    if act == "run":
        # Do not claim a job has run: depending on the Hermes version, `cron run`
        # either fires immediately or marks it for the next ticker tick, and the
        # exit code cannot tell you which. The page watches last_run_at instead.
        return {"status": "asked for", "watch": "last_run_at", "id": job_id, "agent": agent}
    return {"status": act + "d", "id": job_id, "agent": agent}


def register(route, ApiError_):        # noqa: ANN001
    """Declare this module's routes. Called once by server.py at load time."""
    route("GET", "/api/cron")(list_jobs)
    route("POST", "/api/cron/action")(action)
