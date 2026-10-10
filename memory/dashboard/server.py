#!/usr/bin/env python3
"""MIRAI wiki dashboard — the door to the wiki, and the contract behind it.

One server, Python standard library, ThreadingHTTPServer (a route waits on a lock
and must not freeze the page). Bind 127.0.0.1 only.

Routes:
    GET  /                     the wiki page (wiki-page.html, replaced by upload)
    GET  /upload               a small self-contained upload page
    POST /api/upload           receives the file as a base64 data URL
    GET  /api/data             the numbers the page draws (same shape as its demo)
    GET  /api/memory/page      one page's body, read-only, name-gated
    POST /api/memory/lint-now  ask for a lint run
    POST /api/memory/commit    snapshot the wiki into git
    POST /api/drop             the drop door: file or pasted URL into raw/_inbox

Three things engineered around, each one found the hard way by somebody else:
  * drain an oversized request FULLY before refusing it, or the browser shows a
    connection reset instead of your message;
  * finish every response properly, or successful uploads report failure;
  * a name that exists gets a suffix BEFORE the extension (report-2.pdf, never
    report.pdf-2), created with O_EXCL and incrementing on FileExistsError,
    because the server is threaded and a check-then-write race would overwrite
    the only copy.

Writes need the token (X-Wiki-Token, asked once per tab and kept in
sessionStorage). Plainly: it stops a stray local process, not a person with
shell access. Until you add it, anything reaching the port can write.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

WIKI = Path(os.environ.get("CREW_WIKI_DIR", str(Path.home() / "wiki"))).expanduser()
HERE = Path(__file__).resolve().parent
PROJECT = HERE
TOKEN_FILE = PROJECT / "dashboard.token"
PAGE_FILE = PROJECT / "wiki-page.html"
PLACEHOLDER_MARK = "<!-- MIRAI_WIKI_PLACEHOLDER -->"

PORT_DEFAULT = 8899
MAX_UPLOAD = 25 * 1024 * 1024
MAX_DROP = 25 * 1024 * 1024
INBOX_CAP = 200 * 1024 * 1024
DROP_MIN_INTERVAL = 5.0
LINT_MIN_INTERVAL = 300.0

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
PAGE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")

_last_drop = 0.0
_last_lint = 0.0
_lock = threading.Lock()

META_FILES = {"WIKI": WIKI / "WIKI.md", "index": WIKI / "index.md", "log": WIKI / "log.md"}


def token_ok(header: str | None) -> bool:
    if not TOKEN_FILE.exists():
        return True                       # no token configured: open, and the page says so
    try:
        return header == TOKEN_FILE.read_text().strip()
    except OSError:
        return False


def ensure_token() -> str:
    if not TOKEN_FILE.exists():
        TOKEN_FILE.write_text(base64.urlsafe_b64encode(os.urandom(24)).decode())
        os.chmod(TOKEN_FILE, 0o600)
    return TOKEN_FILE.read_text().strip()


def allowed_host(host_header: str | None) -> bool:
    """Reject any Host whose hostname is not 127.0.0.1 or localhost (hostname
    only — the SSH tunnel rewrites ports). That kills DNS rebinding."""
    if not host_header:
        return False
    host = host_header.split(":")[0].strip("[]").lower()
    allowed = {"127.0.0.1", "localhost", "::1"}
    extra = os.environ.get("MIRAI_WIKI_HOSTS", "")   # the tailnet name goes here
    allowed |= {h.strip().lower() for h in extra.split(",") if h.strip()}
    return host in allowed


# ---------------------------------------------------------------------------
# wiki readers
# ---------------------------------------------------------------------------
def _read(path: Path, limit: int | None = None) -> str:
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        return fh.read(limit) if limit else fh.read()


def _summary(path: Path) -> str:
    head = _read(path, 1400)
    for block in head.split("\n\n"):
        block = block.strip()
        if block and not block.startswith(("#", "---", "Source:", "Type:")):
            return " ".join(block.split())[:140]
    return "(no summary yet)"


def _page_files() -> list[tuple[str, str, Path]]:
    """(name, folder, path) for every processed page. Bookkeeping files and
    underscore paths are machinery: never counted, never indexed."""
    out = []
    for folder in ("personal", "business", "research"):
        base = WIKI / "processed" / folder
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.md")):
            rel = p.relative_to(base)
            if any(part.startswith("_") for part in rel.parts):
                continue
            out.append((p.stem, folder + ("/" + rel.parent.as_posix() if rel.parent.as_posix() != "." else ""), p))
    return out


def _wikilinks(text: str) -> list[str]:
    """[[links]] from page bodies. Never from index.md, which links everything
    and would blind the orphan check."""
    return re.findall(r"\[\[([a-z0-9-]+)\]\]", text)


def build_data() -> dict:
    pages = _page_files()
    by_name = {n: (folder, p) for n, folder, p in pages}
    raw_files = sorted((WIKI / "raw").glob("*.md")) if (WIKI / "raw").is_dir() else []

    links: list[dict] = []
    degree: dict[str, int] = {}
    for name, folder, path in pages:
        for target in _wikilinks(_read(path)):
            links.append({"source": name, "target": target})
            degree[name] = degree.get(name, 0) + 1
            degree[target] = degree.get(target, 0) + 1

    nodes = []
    for name, folder, path in pages:
        if folder.startswith("personal"):
            group, parent = "entities", None
        elif folder.startswith("research/concepts"):
            group, parent = "topics", None
        elif folder.startswith("research"):
            group, parent = "library", "owner"
        elif "catalogue" in folder:
            group, parent = "catalogue", "owner"
        else:
            group, parent = "entities", "owner"
        level = 0 if name == "owner" else (1 if "/" not in folder else 2)
        nodes.append({"id": name, "label": name.replace("-", " ").title(), "group": group,
                      "dir": f"processed/{folder}", "excerpt": _summary(path),
                      "mtime": path.stat().st_mtime, "level": level,
                      "degree": 0, "parent": parent})
    for rp in raw_files:
        stem = rp.stem
        nodes.append({"id": stem, "label": stem, "group": "sources", "dir": "raw",
                      "excerpt": "Raw source, filed verbatim, never edited. The research page carries the claims.",
                      "mtime": rp.stat().st_mtime, "level": 4, "degree": 0, "parent": None})

    # ghost links: linked from a page, never written. They are the page's own
    # feature (a red link marks a known gap), so they are reported, not hidden.
    for target in degree:
        if target not in by_name:
            nodes.append({"id": f"ghost:{target}", "label": target.replace("-", " ").title(),
                          "group": "missing", "dir": "", "excerpt": "Linked from a page, never written.",
                          "mtime": 0, "level": 1, "degree": 0, "parent": None})

    log_tail = []
    log_path = WIKI / "log.md"
    if log_path.exists():
        for line in _read(log_path).splitlines()[-40:]:
            parts = [x.strip() for x in line.split("|")]
            if len(parts) >= 3 and not line.startswith("#"):
                log_tail.append({"kind": "update", "stamp": parts[0], "agent": parts[1],
                                 "text": " | ".join(parts[2:])})
    log_tail.reverse()

    lint = _lint_findings()
    depth = max([n["level"] for n in nodes] or [0])
    return {
        "stats": {"pages": len(pages), "sources": len(raw_files), "links": len(links),
                  "log_entries": len(log_tail), "depth": depth},
        "nodes": nodes, "links": links, "log_tail": log_tail, "lint": lint,
    }


def _lint_findings() -> list[str]:
    """The newest dated ## section of _wiki-health.md, as plain sentences."""
    health = WIKI / "_wiki-health.md"
    if not health.exists():
        return []
    sections = re.split(r"^## ", _read(health), flags=re.M)
    if len(sections) < 2:
        return []
    newest = sections[-1]
    head, _, body = newest.partition("\n")
    out = []
    for line in body.splitlines():
        line = line.strip(" -*")
        if line and not line.startswith(("heartbeat", "window-end")):
            out.append(line)
    out.insert(0, f"(lint section {head.strip()})" if head.strip() else "(lint)")
    return out[:12]


def page_body(name: str) -> str:
    if name in META_FILES:
        return _read(META_FILES[name])
    if not PAGE_NAME.match(name):
        raise ValueError("bad page name")
    for folder in ("personal", "business", "research", "research/concepts"):
        p = WIKI / "processed" / folder / f"{name}.md"
        if p.exists():
            return _read(p)
    raise FileNotFoundError(name)


# ---------------------------------------------------------------------------
# writes
# ---------------------------------------------------------------------------
def _unique_name(folder: Path, name: str) -> tuple[Path, str]:
    """Suffix BEFORE the extension, created with O_EXCL, incrementing on
    FileExistsError. Never overwrites."""
    stem, ext = os.path.splitext(name)
    candidate = name
    n = 1
    while True:
        target = folder / candidate
        try:
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.close(fd)
            return target, candidate
        except FileExistsError:
            n += 1
            candidate = f"{stem}-{n}{ext}"
            if n > 500:
                raise RuntimeError("too many collisions in the inbox")


def save_drop(body: dict) -> dict:
    global _last_drop
    with _lock:
        if time.time() - _last_drop < DROP_MIN_INTERVAL:
            raise ValueError("one drop every 5 seconds, please")

    inbox = WIKI / "raw" / "_inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    if sum(f.stat().st_size for f in inbox.iterdir() if f.is_file()) > INBOX_CAP:
        raise ValueError("the inbox is over 200 MB — this box holds the only copy of the wiki")

    if body.get("url"):
        url = str(body["url"]).strip()
        if not re.match(r"^https?://", url):
            raise ValueError("only http and https links")
        stamp = time.strftime("%Y-%m-%d")
        name = f"{stamp}-link.md"
        target, final = _unique_name(inbox, name)
        target.write_text(f"# {url}\n\nSource: {url}\nPasted by the owner {stamp}.\n", encoding="utf-8")
        _stamp_drop()
        return {"saved": final, "kind": "link"}

    raw_name = str(body.get("name") or "")
    if not SAFE_NAME.match(raw_name) or raw_name.startswith(("-", ".")):
        # echo the rejected name only in the response: hostile names travel into
        # shell commands later.
        raise ValueError(f"that file name is not allowed: {raw_name[:60]!r}")
    data = str(body.get("data") or "")
    if "," not in data:
        raise ValueError("file must arrive as a data: URL")
    blob = base64.b64decode(data.split(",", 1)[1])
    if len(blob) > MAX_DROP:
        raise ValueError("over the 25 MB limit")
    target, final = _unique_name(inbox, raw_name)
    target.write_bytes(blob)
    _stamp_drop()
    return {"saved": final, "kind": "file", "bytes": len(blob)}


def _stamp_drop() -> None:
    global _last_drop
    _last_drop = time.time()


def _wiki_cli() -> str | None:
    """The wiki CLI, if this machine has it: its snapshot verb takes the wiki lock,
    which is the whole difference between a clean snapshot and one that races a
    filing. MIRAI_WIKI_CLI pins it for a machine where `wiki` is not on PATH yet."""
    env = os.environ.get("MIRAI_WIKI_CLI")
    if env:
        return env if Path(env).exists() else None
    import shutil
    return shutil.which("wiki")


def snapshot(label: str = "manual snapshot") -> dict:
    if not (WIKI / ".git").exists():
        return {"ok": False, "error": "the wiki is not a git repository yet"}
    try:
        add = subprocess.run(["git", "-C", str(WIKI), "add", "-A"],
                             capture_output=True, text=True, timeout=60)
        if add.returncode != 0:
            return {"ok": False, "error": add.stderr.strip()[:200]}
        diff = subprocess.run(["git", "-C", str(WIKI), "status", "--porcelain"],
                              capture_output=True, text=True, timeout=30).stdout.strip()
        if not diff:
            return {"ok": True, "committed": False, "note": "nothing to snapshot"}
        # A vault snapshot must not fail because this machine has no global git
        # identity: it is the wiki's own snapshot, so the wiki signs it. -c is used
        # rather than git config so the owner's own settings are never touched.
        commit = subprocess.run(["git", "-C", str(WIKI),
                                 "-c", "user.name=MIRAI", "-c", "user.email=mirai@localhost",
                                 "commit", "-m", label],
                                capture_output=True, text=True, timeout=60)
        if commit.returncode != 0:
            return {"ok": False, "error": commit.stderr.strip()[:200]}
        return {"ok": True, "committed": True, "note": commit.stdout.strip().splitlines()[0][:120]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "git took too long — is the wiki locked?"}


def snapshot_via_verb(label: str = "manual snapshot") -> dict | None:
    """Ask the wiki CLI for the snapshot first. It runs the commit inside the wiki's
    own lock, so the button can never race a filing agent, and its exit codes are the
    contract the pack asks for: 3 means busy, and busy means nothing was snapshotted.
    0 with "nothing to snapshot" is a success, not a failure. None means no CLI here:
    the caller falls back to committing directly."""
    cli = _wiki_cli()
    if not cli:
        return None
    runner = [cli] if os.access(cli, os.X_OK) else ["bash", cli]
    try:
        out = subprocess.run(runner + ["snapshot", "--label", label, "--agent", "owner"],
                             capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "wiki is busy, nothing was snapshotted", "phase": "locked"}
    text = (out.stdout or "").strip().splitlines()
    note = text[-1][:160] if text else ""
    if out.returncode == 3:
        return {"ok": False, "error": "wiki is busy, nothing was snapshotted", "phase": "locked"}
    if out.returncode != 0:
        return {"ok": False, "error": (out.stderr or "the snapshot was refused").strip()[:200] or "the snapshot was refused"}
    return {"ok": True, "committed": note.startswith("committed"), "note": note}


def request_lint() -> dict:
    global _last_lint
    with _lock:
        now = time.time()
        if now - _last_lint < LINT_MIN_INTERVAL:
            raise ValueError("one lint request every 5 minutes")
        _last_lint = now
    # The lint is an agent turn. If the Hermes CLI can trigger a cron job on
    # demand we use it; otherwise we leave a request file for the 02:50 job and
    # say so honestly on the button.
    hermes = next((c for c in ("/opt/homebrew/bin/hermes", "/usr/local/bin/hermes",
                               str(Path.home() / ".local/bin/hermes")) if Path(c).exists()), None)
    if hermes:
        try:
            out = subprocess.run([hermes, "cron", "run", "wiki-lint"],
                                 capture_output=True, text=True, timeout=60)
            if out.returncode == 0:
                return {"requested": True, "mode": "fired", "note": "lint asked for now"}
        except subprocess.TimeoutExpired:
            pass
    req = PROJECT / "lint-request.txt"
    req.write_text(time.strftime("%Y-%m-%dT%H:%M:%S\n"), encoding="utf-8")
    return {"requested": True, "mode": "tonight",
            "note": "no on-demand trigger here: the 02:50 job consumes this request"}


# ---------------------------------------------------------------------------
# the http surface
# ---------------------------------------------------------------------------
BODY_CAP = MAX_UPLOAD * 4 // 3 + 4096      # a data: URL spends about a third on base64

KNOWN = {
    "/": ("GET", "HEAD"),
    "/index.html": ("GET", "HEAD"),
    "/upload": ("GET", "HEAD"),
    "/api/data": ("GET",),
    "/api/memory/page": ("GET",),
    "/api/upload": ("POST",),
    "/api/drop": ("POST",),
    "/api/memory/lint-now": ("POST",),
    "/api/memory/commit": ("POST",),
}


class Refused(Exception):
    """A refusal with a status code the owner can act on."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class Handler(BaseHTTPRequestHandler):
    server_version = "mirai-wiki/1.0"
    protocol_version = "HTTP/1.1"

    # -- plumbing -----------------------------------------------------------
    def handle_one_request(self) -> None:
        # A client that hangs up mid-request (a closed tab, a killed curl) must not
        # leave a traceback in the log: that log is read by a human, and a traceback
        # there reads like a crash.
        try:
            super().handle_one_request()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            self.close_connection = True

    def log_message(self, fmt: str, *args) -> None:
        print(f"[wiki] {self.address_string()} {fmt % args}", flush=True)

    # -- replies ------------------------------------------------------------
    def _send(self, code: int, body: bytes, ctype: str,
              extra: dict | None = None, head: bool = False) -> None:
        self.send_response(code)                    # no size argument: the log shows "-"
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if head:
            return
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True

    def _json(self, payload: dict, code: int = 200,
              extra: dict | None = None, head: bool = False) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"
        self._send(code, body, "application/json; charset=utf-8", extra, head)

    def _refuse(self, status: int, message: str) -> None:
        self._json({"ok": False, "error": message}, status)

    # -- who is asking ------------------------------------------------------
    def _token(self) -> str | None:
        header = (self.headers.get("X-Wiki-Token") or "").strip()
        if header:
            return header
        m = re.search(r"(?:^|;\s*)wiki_token=([^;]+)", self.headers.get("Cookie") or "")
        return m.group(1) if m else None

    def _token_ok(self) -> bool:
        return token_ok(self._token())

    def _cookie(self) -> dict:
        """The page's own fetch calls carry no secret: the token is handed over once,
        as an HttpOnly cookie, to the browser that loaded the page from this machine."""
        if not TOKEN_FILE.exists():
            return {}
        try:
            tok = TOKEN_FILE.read_text().strip()
        except OSError:
            return {}
        if not tok or tok == self._token():
            return {}
        return {"Set-Cookie": f"wiki_token={tok}; Path=/; HttpOnly; SameSite=Strict"}

    # -- the body -----------------------------------------------------------
    def _body(self, cap: int = BODY_CAP) -> bytes | None:
        raw = self.headers.get("Content-Length")
        try:
            n = int(raw) if raw else 0
        except ValueError:
            n = -1
        if n < 0:
            self._refuse(400, "bad Content-Length")
            return None
        if n > cap:
            # Drain the whole thing BEFORE refusing, or the sender sees a reset
            # instead of the sentence that explains what happened.
            self._drain(n)
            self._refuse(413, f"over the {MAX_UPLOAD // (1024 * 1024)} MB limit")
            return None
        got = bytearray()
        while len(got) < n:
            chunk = self.rfile.read(min(65536, n - len(got)))
            if not chunk:
                break
            got += chunk
        return bytes(got)

    def _drain(self, n: int) -> None:
        left = max(0, n)
        while left > 0:
            chunk = self.rfile.read(min(65536, left))
            if not chunk:
                return
            left -= len(chunk)

    def _json_body(self, body: bytes) -> dict:
        if not body:
            raise ValueError("the body is empty")
        try:
            obj = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("body is not valid JSON")
        if not isinstance(obj, dict):
            raise ValueError("body must be a JSON object")
        return obj

    # -- routing ------------------------------------------------------------
    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_HEAD(self) -> None:
        self._dispatch("HEAD", head=True)

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str, head: bool = False) -> None:
        split = urlsplit(self.path)
        path = split.path
        if not allowed_host(self.headers.get("Host")):
            self._refuse(403, "this server answers to 127.0.0.1 and localhost only")
            return
        allowed = KNOWN.get(path)
        if allowed is None:
            self._refuse(404, "no such route")
            return
        if method not in allowed:
            self._json({"ok": False, "error": f"{method} is not how this route is asked"},
                       405, {"Allow": ", ".join(allowed)}, head)
            return
        try:
            self._handle(path, parse_qs(split.query), head)
        except Refused as e:
            self._refuse(e.status, e.message)
        except ValueError as e:                     # includes binascii.Error
            self._refuse(400, str(e))
        except FileNotFoundError as e:
            self._refuse(404, f"not on file: {e.args[0] if e.args else path}")
        except OSError as e:
            self._refuse(500, f"the machine refused that: {e.strerror or e}")

    def _handle(self, path: str, qs: dict, head: bool) -> None:
        if path in ("/", "/index.html"):
            page = PAGE_FILE.read_bytes() if PAGE_FILE.exists() else PLACEHOLDER.encode("utf-8")
            self._send(200, page, "text/html; charset=utf-8", self._cookie(), head)
            return
        if path == "/upload":
            self._send(200, UPLOAD_PAGE.encode("utf-8"),
                       "text/html; charset=utf-8", self._cookie(), head)
            return
        if path == "/api/data":
            self._json({"ok": True, **build_data()}, head=head)
            return
        if path == "/api/memory/page":
            name = (qs.get("name") or [""])[0]
            self._json({"ok": True, "name": name, "content": page_body(name)}, head=head)
            return

        # Everything past here writes. The body is drained first and the token comes
        # second, so even a refused request leaves a readable connection behind.
        body = self._body()
        if body is None:
            return
        if not self._token_ok():
            raise Refused(400, "needs the dashboard token (see dashboard.token)")

        if path == "/api/upload":
            self._json({"ok": True, **self._save_page(self._json_body(body))})
            return
        if path == "/api/drop":
            self._json({"ok": True, **save_drop(self._json_body(body))})
            return
        if path == "/api/memory/lint-now":
            self._json({"ok": True, **request_lint()})
            return
        if path == "/api/memory/commit":
            res = snapshot_via_verb() or snapshot()
            if not res.get("ok"):
                raise Refused(409, str(res.get("error") or "the snapshot was refused"))
            self._json({"ok": True, **{k: v for k, v in res.items() if k != "ok"}})
            return
        raise Refused(404, "no such route")

    # -- the one upload that is not a drop ----------------------------------
    def _save_page(self, payload: dict) -> dict:
        name = str(payload.get("name") or "").strip()
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}\.html?$", name):
            raise ValueError("only an .html file is accepted here")
        data = str(payload.get("data") or "")
        if not data.startswith("data:") or "," not in data:
            raise ValueError("the page must arrive as a data: URL")
        blob = base64.b64decode(data.split(",", 1)[1])
        if len(blob) > MAX_UPLOAD:
            raise ValueError("over the 25 MB limit")
        opening = blob[:4096].lower()
        if b"<html" not in opening and b"<!doctype" not in opening:
            raise ValueError("that file does not look like an html page")
        kept = None
        if PAGE_FILE.exists():
            stamp = time.strftime("%Y-%m-%d-%H%M%S")
            kept_path = PAGE_FILE.with_name(f"{PAGE_FILE.name}.{stamp}.bak")
            n = 1
            while kept_path.exists():               # two uploads in the same second
                n += 1
                kept_path = PAGE_FILE.with_name(f"{PAGE_FILE.name}.{stamp}-{n}.bak")
            kept_path.write_bytes(PAGE_FILE.read_bytes())
            kept = kept_path.name
        tmp = PAGE_FILE.with_name(PAGE_FILE.name + ".new")
        tmp.write_bytes(blob)
        os.replace(tmp, PAGE_FILE)                  # the new page either lands whole or not
        return {"bytes": len(blob), "saved": PAGE_FILE.name, "kept": kept}

# The two fallback pages wear the same clothes as the wiki template itself: the same
# oklch palette, the same mono labels, the same rounded-full pills. They are only ever
# seen when wiki-page.html is missing or being replaced, and a fallback that looks like
# a different product reads as a crash.
BASE_CSS = """
:root{--ink:oklch(0.16 0.012 50);--cream:oklch(0.97 0.012 75);--ember:oklch(0.66 0.22 38);
  --ember-soft:oklch(0.78 0.16 50);--surface:oklch(0.93 0.012 75);--border:oklch(0.85 0.012 70)}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:oklch(0.16 0.012 50);
  background-color:oklch(0.96 0.012 75);
  background-image:radial-gradient(900px 600px at 100% 0%,oklch(0.66 0.22 38 / .22),transparent 60%),
    radial-gradient(700px 500px at 0% 100%,oklch(0.16 0.012 50 / .10),transparent 60%),
    linear-gradient(180deg,oklch(0.97 0.012 75) 0%,oklch(0.94 0.014 70) 100%);
  background-attachment:fixed;display:grid;place-items:center;padding:6vh 1.5rem}
.panel{width:min(46rem,100%);border-radius:32px;background:oklch(0.16 0.012 50);color:oklch(0.97 0.012 75);
  padding:34px 36px;position:relative;overflow:hidden}
.panel::after{content:'';position:absolute;top:-90px;right:-60px;width:300px;height:300px;border-radius:50%;
  background:oklch(0.66 0.22 38 / .25);filter:blur(70px);pointer-events:none}
.panel>*{position:relative;z-index:1}
.kicker{display:flex;align-items:center;gap:8px;font-family:'JetBrains Mono',monospace;font-size:10px;
  letter-spacing:.24em;text-transform:uppercase;color:oklch(0.97 0.012 75 / .6);text-decoration:none}
.kicker i{width:7px;height:7px;border-radius:50%;background:oklch(0.66 0.22 38);display:block}
h1{font-family:'Instrument Serif','Times New Roman',serif;font-weight:400;font-size:38px;line-height:1.02;margin:14px 0 0}
h1 span{color:oklch(0.66 0.22 38)}
p{font-size:13.5px;line-height:1.65;color:oklch(0.97 0.012 75 / .72);margin:14px 0 0;max-width:62ch}
code{font-family:'JetBrains Mono',monospace;font-size:12px;background:oklch(0.97 0.012 75 / .08);
  border:1px solid oklch(0.97 0.012 75 / .15);border-radius:6px;padding:1px 6px}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:20px}
input{font:inherit;color:oklch(0.97 0.012 75);background:oklch(0.97 0.012 75 / .08);
  border:1px solid oklch(0.97 0.012 75 / .18);border-radius:999px;padding:10px 16px;width:min(22rem,100%)}
input::placeholder{color:oklch(0.97 0.012 75 / .4)}
input[type=file]{border-radius:20px;padding:8px 14px;width:auto}
button{font-family:'JetBrains Mono',monospace;font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;
  height:40px;padding:0 20px;border-radius:999px;cursor:pointer;background:oklch(0.66 0.22 38);
  color:oklch(0.97 0.012 75);border:1px solid oklch(0.66 0.22 38);transition:background-color .18s}
button:hover{background:oklch(0.78 0.16 50);border-color:oklch(0.78 0.16 50)}
.msg{font-family:'JetBrains Mono',monospace;font-size:10.5px;letter-spacing:.08em;
  color:oklch(0.97 0.012 75 / .7);margin-top:14px;min-height:1.2em}
a.kicker:hover{color:oklch(0.78 0.16 50)}
"""


PLACEHOLDER = ("<!doctype html><meta charset='utf-8'><title>MIRAI wiki</title>"
               "<meta name='viewport' content='width=device-width,initial-scale=1'>"
               "<style>" + BASE_CSS + "</style>"
               + PLACEHOLDER_MARK +
               "<div class='panel'><div class='kicker'><i></i> MIRAI &middot; wiki dashboard</div>"
               "<h1>The vault is being <span>rebuilt.</span></h1>"
               "<p>The designed wiki page (<code>wiki-page.html</code>) is not in this folder, so there is "
               "nothing designed to serve yet. Everything behind it still answers: the graph data, the pages, "
               "the drop door.</p>"
               "<p>Put the delivered page here as <code>wiki-page.html</code>, or send it through "
               "<a class='kicker' href='/upload' style='display:inline-flex'><i></i> /upload</a>, and reload. "
               "The file is read per request, so there is no restart.</p>"
               "<div class='row'><a class='kicker' href='/api/data'><i></i> /api/data</a>"
               "<a class='kicker' href='/upload'><i></i> /upload</a></div></div>")


UPLOAD_PAGE = """<!doctype html><meta charset="utf-8"><title>Upload the wiki page</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>""" + BASE_CSS + """</style>
<div class="panel">
  <div class="kicker"><i></i> MIRAI &middot; wiki dashboard &middot; install</div>
  <h1>Put the designed page <span>here.</span></h1>
  <p>The dashboard is ONE self-contained HTML file. Whatever you pick is saved as <code>wiki-page.html</code>,
  and the previous one is kept beside it with a timestamp, so nothing is overwritten in place.</p>
  <div class="row"><input id="t" placeholder="paste the token from dashboard.token"></div>
  <div class="row"><input type="file" id="f" accept=".html,.htm"><button id="go">Upload it</button></div>
  <div class="msg" id="msg"></div>
</div>
<script>
document.getElementById('go').onclick = async () => {
  const f = document.getElementById('f').files[0];
  const msg = document.getElementById('msg');
  if (!f) { msg.textContent = 'pick a file first'; return; }
  msg.textContent = 'reading the file';
  const text = await f.text();
  const data = 'data:text/html;base64,' + btoa(unescape(encodeURIComponent(text)));
  try {
    const r = await fetch('/api/upload', {method:'POST',
      headers:{'Content-Type':'application/json','X-Wiki-Token':document.getElementById('t').value},
      body: JSON.stringify({name: f.name, data})});
    const j = await r.json();
    msg.textContent = j.ok ? ('saved ' + j.bytes + ' bytes, open /') : ('refused: ' + j.error);
  } catch (e) { msg.textContent = 'failed: ' + e.message; }
};
</script>
</body>"""



def main() -> int:
    port = int(os.environ.get("MIRAI_WIKI_PORT", os.sys.argv[1] if len(os.sys.argv) > 1 else PORT_DEFAULT))
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        print(f"[wiki] port {port} is taken ({e}). Find the owner with: "
              f"lsof -nP -iTCP:{port} -sTCP:LISTEN")
        return 1
    print(f"[wiki] dashboard on http://127.0.0.1:{port} — wiki at {WIKI}")
    if TOKEN_FILE.exists():
        print(f"[wiki] writes need the token in {TOKEN_FILE} (0600)")
    else:
        print("[wiki] no token file yet: writes are open to anything on this port. "
              "Run: python3 -c \"import server; print(server.ensure_token())\"")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
