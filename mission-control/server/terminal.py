"""terminal.py — a real shell, streamed to the page.

Shape, given rather than implied: ONE reader thread per session owns the pty
master and writes into a ring buffer. Streams read the RING, never the fd.
Anything else loses output written while no tab is connected, and makes two tabs
race for the same bytes.

pty.fork(), not os.fork() plus openpty: otherwise the shell has no controlling
terminal and job control is silently off until somebody presses Ctrl-C. TERM is
set in the child, or xterm.js renders no colour.

os.read on the master raises OSError EIO when the child exits. That is the
normal end of a shell, not an error, so it is not logged as one.
"""
from __future__ import annotations

import base64
import errno
import fcntl
import json
import os
import re
import select
import signal
import struct
import termios
import threading
import time
import uuid
from pathlib import Path

import store
from server import ApiError, Stream

MIRAI_DIR = Path(os.environ.get("MIRAI_DIR", str(Path.home() / "mirai"))).expanduser()
DATA_DIR = Path(os.environ.get("MIRAI_DATA_DIR", str(MIRAI_DIR / "data"))).expanduser()
QUICK_FILE = DATA_DIR / "quick-commands.json"

RUNTIMES = {"shell": None, "bash": "/bin/bash", "python": "python3", "node": "node"}
RING_BYTES = 64 * 1024
IDLE_CLOSE_S = 3600


class Session:
    def __init__(self, sid: str, runtime: str, cols: int, rows: int):
        self.id = sid
        self.runtime = runtime
        self.created = time.time()
        self.last_stream = time.time()
        self.ring = bytearray()
        self.seq = 0                     # monotonic; every chunk's sequence number
        self.first_seq = 1
        self.exited = False
        self.exit_code = None
        self.lock = threading.Lock()
        self.data_event = threading.Event()

        env = dict(os.environ)
        env["TERM"] = "xterm-256color"
        env.pop("MIRAI_DASHBOARD", None)

        pid, master = _pty_fork(runtime, cols, rows, env)
        self.pid = pid
        self.master = master
        self.reader = threading.Thread(target=self._read_loop, daemon=True)
        self.reader.start()

    # -- reading ---------------------------------------------------------
    def _read_loop(self) -> None:
        while True:
            try:
                ready, _, _ = select.select([self.master], [], [], 1.0)
                if not ready:
                    continue
                chunk = os.read(self.master, 65536)
            except OSError as e:
                if e.errno == errno.EIO:
                    self._finish(0)      # the normal end of a shell
                elif e.errno in (errno.EBADF,):
                    self._finish(None)
                break
            if not chunk:
                self._finish(0)
                break
            with self.lock:
                self.seq += 1
                self.ring += chunk
                if len(self.ring) > RING_BYTES:
                    drop = len(self.ring) - RING_BYTES
                    del self.ring[:drop]
                    self.first_seq = max(1, self.first_seq + 1)
            self.data_event.set()
            self.data_event.clear()

    def _finish(self, code: int | None) -> None:
        self.exited = True
        self.exit_code = code
        try:
            _, status = os.waitpid(self.pid, os.WNOHANG)
            if status:
                self.exit_code = os.waitstatus_to_exitcode(status) if hasattr(os, "waitstatus_to_exitcode") else code
        except OSError:
            pass
        self.data_event.set()
        self.data_event.clear()

    # -- io --------------------------------------------------------------
    def write(self, data: str) -> None:
        blob = data.encode("utf-8", errors="replace")
        view = memoryview(blob)
        while view:                      # os.write to a pty can be short
            try:
                n = os.write(self.master, view)
            except OSError:
                return
            view = view[n:]

    def resize(self, cols: int, rows: int) -> None:
        try:
            fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except OSError:
            pass

    def chunks_since(self, last_seq: int):
        """Yield (seq, chunk). A stream that has fallen behind the ring gets a
        gap report rather than a lie."""
        with self.lock:
            if last_seq and last_seq < self.first_seq - 1:
                dropped = self.first_seq - 1 - last_seq
                yield (None, dropped)
            start = self.ring[:]
            base_seq = self.seq
        yield (base_seq, bytes(start))

    def close(self) -> None:
        """Signal the process GROUP, not the pid, or the shell's children outlive it."""
        for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(os.getpgid(self.pid), sig)
            except OSError:
                return
            for _ in range(10):
                time.sleep(0.05)
                try:
                    os.kill(self.pid, 0)
                except OSError:
                    return
        try:
            os.close(self.master)
        except OSError:
            pass


def _pty_fork(runtime: str, cols: int, rows: int, env: dict):
    argv = None
    if RUNTIMES[runtime]:
        argv = [RUNTIMES[runtime]]
    pid, master = os.forkpty() if hasattr(os, "forkpty") else (None, None)
    if pid == 0:                          # child
        try:
            if not argv:
                shell = os.environ.get("SHELL", "/bin/zsh" if sys_platform_is_mac() else "/bin/bash")
                os.execvpe(shell, [shell, "-l"], env)
            else:
                os.execvpe(argv[0], argv, env)
        except Exception:
            os._exit(127)
    if cols and rows:
        try:
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except OSError:
            pass
    return pid, master


def sys_platform_is_mac() -> bool:
    import sys
    return sys.platform == "darwin"


_sessions: dict[str, Session] = {}
_sessions_lock = threading.Lock()


def _reap_loop() -> None:
    """Reaping is two jobs: waitpid every child or collect zombies for the life
    of the process, and separately close sessions nobody has streamed from."""
    while True:
        time.sleep(30)
        with _sessions_lock:
            for sid, s in list(_sessions.items()):
                if s.exited and (time.time() - s.last_stream) > 120:
                    _sessions.pop(sid, None)
                    try:
                        os.waitpid(s.pid, os.WNOHANG)
                    except OSError:
                        pass
                elif (time.time() - s.last_stream) > IDLE_CLOSE_S:
                    s.close()
                    _sessions.pop(sid, None)


threading.Thread(target=_reap_loop, daemon=True).start()


def open_session(req, query, body):         # noqa: ANN001
    if body is None:
        body = {}
    runtime = str(body.get("runtime") or "shell").lower()
    if runtime not in RUNTIMES:
        raise ApiError(400, f"runtime must be one of: {', '.join(RUNTIMES)}")
    cols = int(body.get("cols") or 80)
    rows = int(body.get("rows") or 24)
    sid = body.get("id")

    resumed = False
    with _sessions_lock:
        if sid and sid in _sessions and not _sessions[sid].exited:
            s = _sessions[sid]
            resumed = True
        else:
            s = Session(uuid.uuid4().hex[:12], runtime, cols, rows)
            _sessions[s.id] = s
    s.last_stream = time.time()
    return {"resumed": resumed,
            "session": {"id": s.id, "pid": s.pid, "user": os.environ.get("USER", "user"),
                        "host": os.uname().nodename,
                        "home": str(Path.home()), "runtime": runtime}}


def stream(req, query, body):               # noqa: ANN001
    sid = query.get("id") or ""
    with _sessions_lock:
        s = _sessions.get(sid)
    if not s:
        raise ApiError(404, "no such session")
    try:
        last = int(req.headers.get("Last-Event-ID") or query.get("last") or 0)
    except ValueError:
        last = 0

    def gen():
        sent_seq = last
        while True:
            s.last_stream = time.time()
            for seq, chunk in s.chunks_since(sent_seq):
                if seq is None:
                    yield f"event: gap\ndata: {json.dumps({'dropped': chunk})}\n\n"
                    sent_seq = s.first_seq - 1
                elif chunk:
                    # No event name: the page reads these with es.onmessage,
                    # which never fires for a named event.
                    yield f"id: {seq}\ndata: {base64.b64encode(chunk).decode()}\n\n"
                    sent_seq = seq
            if s.exited:
                yield f"event: exit\ndata: {json.dumps({'code': s.exit_code})}\n\n"
                return
            yield ": keep-alive\n\n"      # an idle shell must not look like a dead proxy
            s.data_event.wait(timeout=15)

    return Stream(gen(), "text/event-stream", {"X-Accel-Buffering": "no"})


def input_route(req, query, body):          # noqa: ANN001
    if body is None:
        body = {}
    s = _get(body.get("id"))
    s.write(str(body.get("data") or ""))
    return {"sent": len(str(body.get("data") or ""))}


def resize(req, query, body):               # noqa: ANN001
    if body is None:
        body = {}
    s = _get(body.get("id"))
    s.resize(int(body.get("cols") or 80), int(body.get("rows") or 24))
    return {"cols": body.get("cols"), "rows": body.get("rows")}


def close(req, query, body):                # noqa: ANN001
    if body is None:
        body = {}
    sid = str(body.get("id") or "")
    with _sessions_lock:
        s = _sessions.pop(sid, None)
    if s:
        s.close()
    return {"closed": bool(s)}


def list_sessions(req, query, body):        # noqa: ANN001
    with _sessions_lock:
        items = [{"id": s.id, "pid": s.pid, "runtime": s.runtime, "exited": s.exited,
                  "created": s.created, "age_s": round(time.time() - s.created, 1)}
                 for s in _sessions.values()]
    return {"sessions": items, "count": len(items)}


def _get(sid) -> Session:
    with _sessions_lock:
        s = _sessions.get(str(sid or ""))
    if not s:
        raise ApiError(404, "no such session")
    return s


def commands(req, query, body):             # noqa: ANN001
    return {"commands": _load_commands()}


def commands_post(req, query, body):        # noqa: ANN001
    if body is None:
        body = {}
    items = _load_commands()
    if body.get("remove"):
        rid = str(body["remove"])
        items = [c for c in items if c.get("id") != rid]
        _save_commands(items)
        return {"commands": items}
    label = str(body.get("label") or "").strip()
    command = str(body.get("command") or "").strip()
    if not label or not command:
        raise ApiError(400, "label and command are required")
    if len(label) > 40:
        raise ApiError(400, "label is limited to 40 characters")
    if len(command) > 500:
        raise ApiError(400, "command is limited to 500 characters")
    if "\n" in label or "\n" in command:
        raise ApiError(400, "one line each")
    if len(items) >= 30:
        raise ApiError(400, "at most 30 quick commands")
    items.append({"id": uuid.uuid4().hex[:8], "label": label, "command": command})
    _save_commands(items)
    return {"commands": items}


def _load_commands() -> list[dict]:
    try:
        data = json.loads(QUICK_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_commands(items: list[dict]) -> None:
    QUICK_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUICK_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")


def register(route, ApiError_):        # noqa: ANN001
    """Declare this module's routes. Called once by server.py at load time."""
    route("POST", "/api/terminal/open")(open_session)
    route("GET", "/api/terminal/stream")(stream)
    route("POST", "/api/terminal/input")(input_route)
    route("POST", "/api/terminal/resize")(resize)
    route("POST", "/api/terminal/close")(close)
    route("GET", "/api/terminal/list")(list_sessions)
    route("GET", "/api/terminal/commands")(commands)
    route("POST", "/api/terminal/commands")(commands_post)
