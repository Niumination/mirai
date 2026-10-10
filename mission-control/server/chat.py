"""chat.py — one real turn, to a real agent.

The command, in full, because every flag is on a SUBCOMMAND and none is top
level (written any other way the CLI says your text is not a hermes command):

    hermes [-p <profile>] chat -q "<text>" -Q --source mirai \
           -c mirai-<agent> --create-if-missing [--image <path>]

-Q is the difference between parsing an answer and parsing a screenshot: without
it you get a banner, a box, a Reasoning panel and a "Resume this session with"
footer around every reply. With it you still get one line before the answer —
`session_id: <id>` — so it is stripped. The CLI also prints its own chatter
("tirith security scanner enabled…") to stdout ahead of the answer, so all of it
is cleaned rather than trusted.

One turn is one subprocess, run to completion, 300 second timeout. One turn at a
time per agent (a lock per profile); different agents run in parallel.
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import store
from server import ApiError, Raw

MIRAI_DIR = Path(os.environ.get("MIRAI_DIR", str(Path.home() / "mirai"))).expanduser()
DATA_DIR = Path(os.environ.get("MIRAI_DATA_DIR", str(MIRAI_DIR / "data"))).expanduser()
CHAT_FILES = DATA_DIR / "chat-files"

SOURCE = "mirai"                    # the literal string other integrations must never share
MAX_CHARS = 6000                    # what we send
TIMEOUT_S = 300
MAX_FILE_BYTES = 8 * 1024 * 1024    # decoded, per file
MAX_MESSAGE_BYTES = 16 * 1024 * 1024
MAX_FILES = 4
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf", ".txt", ".md",
               ".csv", ".json", ".zip", ".docx", ".xlsx", ".mp3", ".wav", ".m4a"}

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()
_running: dict[str, float] = {}     # agent code -> started_at while a turn is in flight

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations(
  agent TEXT PRIMARY KEY,
  name TEXT NOT NULL,               -- the -c session name we keep for it
  updated_at REAL NOT NULL
);
"""

store.ensure(_SCHEMA, "chat")

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
NOISE_LINES = (
    "session_id:", "resume this session", "tirith", "security scanner",
    "warning:", "deprecationwarning", "reasoning", "thinking…", "thinking...",
)


def _lock_for(agent: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(agent, threading.Lock())


def _find_hermes() -> str:
    """Never rely on a bare 'hermes': launchd does not put ~/.local/bin (or Homebrew) on PATH."""
    for cand in ("/opt/homebrew/bin/hermes", "/usr/local/bin/hermes",
                 str(Path.home() / ".local" / "bin" / "hermes"), "/usr/bin/hermes"):
        if Path(cand).exists():
            return cand
    found = shutil.which("hermes")
    if found:
        return found
    raise ApiError(503, "hermes CLI not found (looked in /opt/homebrew/bin, /usr/local/bin, "
                        "~/.local/bin, /usr/bin and PATH)")


def _profile_of(agent_code: str) -> str:
    import roster
    profile = roster.profile_of_code(agent_code)
    if profile:
        return profile
    # Accept a profile name directly (handy from curl), and "default".
    return agent_code if agent_code in roster.profiles() else agent_code.lower()


def _conversation_name(agent: str) -> str:
    row = store.one("SELECT name FROM conversations WHERE agent=?", (agent,))
    if row:
        return row["name"]
    name = f"mirai-{agent.lower()}"
    store.execute("INSERT OR REPLACE INTO conversations(agent, name, updated_at) VALUES(?,?,?)",
                  (agent, name, time.time()))
    return name


def _session_name(agent: str) -> str:
    return _conversation_name(agent.lower() if agent.isupper() else agent)


def _clean(text: str) -> str:
    text = ANSI_RE.sub("", text)
    lines = []
    for line in text.splitlines():
        low = line.strip().lower()
        if not low:
            lines.append(line)
            continue
        if low.startswith("session_id:"):
            continue
        if any(n in low for n in NOISE_LINES) and len(low) < 140:
            continue
        lines.append(line)
    out = "\n".join(lines).strip()
    return out


# ---------------------------------------------------------------------------
# Attachments (prompt 18)
# ---------------------------------------------------------------------------
def _decode_data_url(data: str) -> bytes | None:
    if not isinstance(data, str) or "," not in data:
        return None
    try:
        head, payload = data.split(",", 1)
        if ";base64" in head:
            return base64.b64decode(payload)
        return payload.encode("utf-8")
    except Exception:
        return None


def _keep_files(agent: str, items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Returns (kept, dropped). Applied in order: file size, then count, then total."""
    kept: list[dict] = []
    dropped: list[dict] = []
    total = 0
    CHAT_FILES.mkdir(parents=True, exist_ok=True)
    for item in items:
        name = str(item.get("name") or "file")
        blob = _decode_data_url(item.get("data") or "")
        if blob is None:
            dropped.append({"name": name, "reason": "unreadable attachment"})
            continue
        if len(blob) > MAX_FILE_BYTES:
            dropped.append({"name": name, "reason": "over the 8 MB per-file limit"})
            continue
        if len(kept) >= MAX_FILES:
            dropped.append({"name": name, "reason": "over the 4 file limit for one message"})
            continue
        if total + len(blob) > MAX_MESSAGE_BYTES:
            dropped.append({"name": name, "reason": "over the 16 MB per-message total"})
            continue
        ext = Path(name).suffix.lower() or ".bin"
        if ext not in ALLOWED_EXT:
            ext = ".bin"
        fid = uuid.uuid4().hex
        target = CHAT_FILES / f"{fid}{ext}"
        target.write_bytes(blob)
        kept.append({"name": name, "type": item.get("type") or "application/octet-stream",
                     "size": len(blob), "url": f"/api/chat/file?id={fid}{ext}",
                     "path": str(target), "id": f"{fid}{ext}"})
        total += len(blob)
    return kept, dropped


def _send_turn(agent: str, text: str, files: list[dict]) -> str:
    profile = _profile_of(agent)
    convo = _session_name(agent)

    body = text[:MAX_CHARS]
    if files:
        described = "\n\nAttached files (saved on this machine, open them with your file tools):\n"
        for f in files:
            described += f"- {f['name']} ({f['type']}, {f['size']} bytes) at {f['path']}\n"
        body += described

    cmd = [_find_hermes()]
    if profile != "default":
        cmd += ["-p", profile]
    cmd += ["chat", "-q", body, "-Q", "--source", SOURCE, "-c", convo, "--create-if-missing"]

    image = next((f for f in files if Path(f["name"]).suffix.lower()
                  in (".png", ".jpg", ".jpeg", ".webp", ".gif")), None)
    if image:
        cmd += ["--image", image["path"]]

    env = dict(os.environ)
    env["PATH"] = env.get("PATH", "") + ":/opt/homebrew/bin:/usr/local/bin:" + str(Path.home() / ".local" / "bin")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S, env=env)
    except subprocess.TimeoutExpired:
        raise ApiError(504, f"{agent} did not finish within {TIMEOUT_S}s")
    except OSError as e:
        raise ApiError(503, f"could not run hermes: {e}")

    reply = _clean((proc.stdout or "") + ("\n" + proc.stderr if proc.returncode and proc.stderr else ""))
    # Judge success by the reply text, not the exit code: hermes exits 0 with no output.
    if not reply:
        raise ApiError(502, f"{agent} produced no answer (exit {proc.returncode}) — "
                            f"check that its profile has a login (auth.json)")
    return reply


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def post_chat(req, query, body):            # noqa: ANN001
    if body is None:
        body = {}
    agent = str(body.get("agent") or "").strip()
    if not agent:
        raise ApiError(400, "agent is required (a two letter code, e.g. EX)")
    text = str(body.get("text") or "").strip()
    items = body.get("files") or body.get("attachments") or []
    if not isinstance(items, list):
        raise ApiError(400, "files must be a list")
    if not text and not items:
        raise ApiError(400, "text or at least one file is required")

    kept, dropped = _keep_files(agent, items)

    lock = _lock_for(agent)
    if not lock.acquire(timeout=TIMEOUT_S):
        raise ApiError(429, f"{agent} is busy with another turn")
    started = time.time()
    _running[agent] = started
    try:
        reply = _send_turn(agent, text, kept)
    finally:
        _running.pop(agent, None)
        lock.release()
    ms = round((time.time() - started) * 1000, 1)

    convo = _session_name(agent)
    store.execute(
        "INSERT INTO turns(at, agent, source, conversation, role, text, ms, files) VALUES(?,?,?,?,?,?,?,?)",
        (started, agent, SOURCE, convo, "you", text, None, json.dumps(_public_files(kept))))
    store.execute(
        "INSERT INTO turns(at, agent, source, conversation, role, text, ms, files) VALUES(?,?,?,?,?,?,?,?)",
        (time.time(), agent, SOURCE, convo, "agent", reply, ms, None))

    out = {"reply": reply, "agent": agent, "ms": ms, "conversation": convo}
    if dropped:
        out["dropped"] = dropped
        out["note"] = ("some attachments were left behind: " + "; ".join(
            f"{d['name']} — {d['reason']}" for d in dropped) +
            ". Base64 is a third bigger than the bytes it carries, so a message at the full "
            "16 MB is the practical ceiling here.")
    return out


def _public_files(files: list[dict]) -> list[dict]:
    return [{"name": f["name"], "type": f["type"], "size": f["size"], "url": f["url"]} for f in files]


def get_history(req, query, body):          # noqa: ANN001
    import roster
    agent = query.get("agent") or ""
    try:
        limit = min(400, max(1, int(query.get("limit") or 80)))
    except ValueError:
        raise ApiError(400, "limit must be a number")
    if not agent:
        raise ApiError(400, "agent is required")

    convo = _session_name(agent)
    # Tag every turn with the conversation it was sent under, and return only the
    # current name's turns. Untagged turns count as the first conversation.
    rows = store.query(
        "SELECT role, text, at, ms, files FROM turns "
        "WHERE agent=? AND source=? AND (conversation=? OR conversation IS NULL) "
        "ORDER BY id DESC LIMIT ?", (agent, SOURCE, convo, limit))
    rows.reverse()                          # handed back oldest first
    messages = []
    for r in rows:
        files = None
        if r["files"]:
            try:
                files = json.loads(r["files"])
            except Exception:
                files = None
        messages.append({"role": r["role"], "text": r["text"], "at": r["at"],
                         "ms": r["ms"], "files": files})
    thinking = agent in _running
    return {"agent": agent, "conversation": convo, "messages": messages, "thinking": thinking,
            "code": roster.code_of(agent) or agent}


def post_forget(req, query, body):          # noqa: ANN001
    if body is None:
        body = {}
    agent = str(body.get("agent") or "").strip()
    if not agent:
        raise ApiError(400, "agent is required")
    new_name = f"mirai-{agent.lower()}-{int(time.time())}"
    # Nothing under ~/.hermes is deleted: the name changes, so the next turn
    # opens a fresh conversation.
    store.execute("INSERT OR REPLACE INTO conversations(agent, name, updated_at) VALUES(?,?,?)",
                  (agent, new_name, time.time()))
    store.audit("operator", "chat.forget", {"agent": agent, "conversation": new_name})
    return {"agent": agent, "conversation": new_name}


def get_file(req, query, body):             # noqa: ANN001
    name = query.get("id") or ""
    if not re.match(r"^[0-9a-f]{32}(\.[A-Za-z0-9]{1,8})?$", name):
        raise ApiError(400, "bad file id")
    path = (CHAT_FILES / name).resolve()
    if CHAT_FILES.resolve() not in path.parents or not path.exists():
        raise ApiError(404, "no such file")
    ctype = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".gif": "image/gif", ".pdf": "application/pdf",
        ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8",
        ".csv": "text/csv", ".json": "application/json",
    }.get(path.suffix.lower(), "application/octet-stream")
    return Raw(path.read_bytes(), ctype,
               {"Content-Disposition": f'inline; filename="{quote(path.name)}"'})


def register(route, ApiError_):        # noqa: ANN001
    """Declare this module's routes. Called once by server.py at load time."""
    route("POST", "/api/chat")(post_chat)
    route("GET", "/api/chat/history")(get_history)
    route("POST", "/api/chat/forget")(post_forget)
    route("GET", "/api/chat/file")(get_file)
