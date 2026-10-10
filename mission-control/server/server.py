#!/usr/bin/env python3
"""MIRAI Mission Control — the only HTTP server in this build.

Run as a script:
    python3 server.py 8800            # port from argv[1], default 8800

Nothing else in ~/mirai/server opens a socket. Every module declares its own
routes through register(route, ApiError) and this file dispatches them.

Two notes that cost hours when they are rediscovered instead of read:
  * sys.modules.setdefault below. This file runs as __main__; a module doing
    `import server` would otherwise get a SECOND copy with its own ROUTES dict
    and its own ApiError class, so its registrations land nowhere and an
    isinstance check against ApiError silently fails. One line, one module.
  * Responses that are not JSON go out as Raw(...) or Stream(...) rather than
    a per-module invention, because three features need them: attachments
    serve a file, voice returns audio with its own header, the terminal streams.
"""
from __future__ import annotations

import gzip
import json
import os
import socket
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

# ---------------------------------------------------------------------------
# One module, not two. See the docstring.
# ---------------------------------------------------------------------------
sys.modules.setdefault("server", sys.modules["__main__"])

PORT_DEFAULT = 8800
MAX_BODY_BYTES = 30 * 1024 * 1024        # 30 MB, refused BEFORE the body is read
STARTED_AT = time.time()

# Where our own state lives. Never mixed with Hermes state, which is read only.
MIRAI_DIR = Path(os.environ.get("MIRAI_DIR", str(Path.home() / "mirai"))).expanduser()
DATA_DIR = MIRAI_DIR / "data"

ROUTES: dict[tuple[str, str], callable] = {}
RAW_BODY_PATHS: set[str] = set()        # routes that receive raw bytes, not JSON

# Modules loaded in this order. Missing files are skipped, so the server runs
# from the first card and every later module is picked up with no extra wiring.
MODULES = (
    "settings", "avatars", "chat", "voice", "missions", "workforce", "cron",
    "docs", "health", "traffic", "files", "terminal", "models",
)


class ApiError(Exception):
    """Every failure in this build is raised as this, never printed and swallowed."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class Raw:
    """Send bytes as-is: a file, audio, a download."""

    def __init__(self, body: bytes, content_type: str = "application/octet-stream",
                 headers: dict | None = None):
        self.body = body
        self.content_type = content_type
        self.headers = headers or {}


class Stream:
    """Send a generator as server-sent events / chunked text."""

    def __init__(self, generator, content_type: str = "text/event-stream",
                 headers: dict | None = None):
        self.generator = generator
        self.content_type = content_type
        self.headers = headers or {}


def route(method: str, path: str):
    """Decorator that fills ROUTES. One method + one path per entry."""
    def deco(fn):
        ROUTES[(method.upper(), path)] = fn
        return fn
    return deco


def json_bytes(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")


# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------
def _register_fleet_route() -> None:
    """roster.py has no routes of its own, so the fleet endpoint is declared here.

    GET /api/agents is the product's pulse: the dashboard treats two failures in
    a row as "MIRAI is out of reach" on every page.
    """
    try:
        import roster
    except Exception:
        print("[server] roster failed to load:")
        traceback.print_exc()
        return

    @route("GET", "/api/agents")
    def _agents(req, query, body):          # noqa: ANN001
        force = str(query.get("force", "")).lower() in ("1", "true", "yes")
        return roster.agents(force=force)


def _register_floor_routes() -> None:
    @route("GET", "/api/ping")
    def _ping(req, query, body):            # noqa: ANN001
        return {"uptime_s": round(time.time() - STARTED_AT, 3)}


def _load_modules() -> int:
    here = Path(__file__).resolve().parent
    loaded = 0
    for name in MODULES:
        if not (here / f"{name}.py").exists():
            continue
        try:
            mod = __import__(name)
            mod.register(route, ApiError)
            if getattr(mod, "RAW_BODY_PATHS", None):
                for p in mod.RAW_BODY_PATHS:
                    RAW_BODY_PATHS.add(p)
            loaded += 1
        except Exception:                      # a broken module must not kill the server
            print(f"[server] module {name} failed to load:")
            traceback.print_exc()
    return loaded


# ---------------------------------------------------------------------------
# The one page we serve: the dashboard, read per request so replacing the file
# never needs a restart.
# ---------------------------------------------------------------------------
def _dashboard_file() -> Path:
    return MIRAI_DIR / "dashboard.html"


def _etag_for(path: Path) -> str:
    st = path.stat()
    return f'W/"{int(st.st_mtime)}-{st.st_size}"'



# The sign-in page: what an unauthenticated browser gets when the gate is on. It is
# not the dashboard and it is not raw JSON either - a person who typed the address
# deserves a page that says what to do and a field to do it in. Submitting it lands
# on "/?k=<token>", which is the one-tap link the gate already understands.
SIGNIN_PAGE = """<!doctype html><meta charset="utf-8"><title>MIRAI — sign in</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--ink:oklch(0.16 0.012 50);--cream:oklch(0.97 0.012 75);--ember:oklch(0.66 0.22 38)}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:var(--ink);
  background-color:oklch(0.96 0.012 75);
  background-image:radial-gradient(900px 600px at 100% 0%,oklch(0.66 0.22 38 / .22),transparent 60%),
    linear-gradient(180deg,oklch(0.97 0.012 75) 0%,oklch(0.94 0.014 70) 100%);
  background-attachment:fixed;display:grid;place-items:center;padding:6vh 1.5rem}
.panel{width:min(40rem,100%);border-radius:32px;background:oklch(0.16 0.012 50);color:oklch(0.97 0.012 75);
  padding:34px 36px;position:relative;overflow:hidden}
.panel::after{content:'';position:absolute;top:-90px;right:-60px;width:300px;height:300px;border-radius:50%;
  background:oklch(0.66 0.22 38 / .25);filter:blur(70px);pointer-events:none}
.panel>*{position:relative;z-index:1}
.kicker{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:.24em;text-transform:uppercase;
  color:oklch(0.97 0.012 75 / .6)}
h1{font-family:'Instrument Serif','Times New Roman',serif;font-weight:400;font-size:36px;line-height:1.02;margin:12px 0 0}
h1 span{color:oklch(0.66 0.22 38)}
p{font-size:13.5px;line-height:1.65;color:oklch(0.97 0.012 75 / .72);margin:14px 0 0;max-width:60ch}
code{font-family:'JetBrains Mono',monospace;font-size:12px;background:oklch(0.97 0.012 75 / .08);
  border:1px solid oklch(0.97 0.012 75 / .15);border-radius:6px;padding:1px 6px}
form{display:flex;gap:10px;flex-wrap:wrap;margin-top:20px}
input{font:inherit;color:oklch(0.97 0.012 75);background:oklch(0.97 0.012 75 / .08);
  border:1px solid oklch(0.97 0.012 75 / .18);border-radius:999px;padding:10px 16px;width:min(22rem,100%)}
button{font-family:'JetBrains Mono',monospace;font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;
  height:40px;padding:0 20px;border-radius:999px;cursor:pointer;background:oklch(0.66 0.22 38);
  color:oklch(0.97 0.012 75);border:1px solid oklch(0.66 0.22 38)}
a{color:oklch(0.78 0.16 50)}
</style>
<div class="panel">
  <div class="kicker">MIRAI · mission control</div>
  <h1>The door is <span>locked.</span></h1>
  <p>This console is behind the token gate (<code>MIRAI_AUTH=on</code>). Paste the token,
  or open the link <code>~/mirai/link.sh</code> printed — either way the browser remembers
  it for thirty days.</p>
  <form method="get" action="/">
    <input name="k" placeholder="paste the token" autofocus autocomplete="off">
    <button type="submit">Open the console</button>
  </form>
  <p style="font-size:11.5px">The token is in <code>~/mirai/data/auth.token</code>, mode 0600.
  Nothing else on this machine can read it, and this page never prints it back.</p>
</div>
</body>
"""


def _host_ok(host_header: str | None) -> bool:
    """Reject any Host whose hostname is not this machine or a name the owner listed.

    The bind is 127.0.0.1, so in theory nothing else can reach us -- but a browser on
    this machine will happily follow a DNS-rebinding name to 127.0.0.1 and then talk to
    us as if it were "attacker.example". One line of check kills that. The tailnet name
    goes in MIRAI_HOSTS (set by scripts/tailscale-serve.sh), because Tailscale is a
    proxy in front of the loopback server and its Host header is the tailnet name.
    Hostname only: a proxy may legitimately rewrite the port."""
    if not host_header:
        return False
    host = host_header.split(":")[0].strip("[]").lower()
    allowed = {"127.0.0.1", "localhost", "::1", ""}
    extra = os.environ.get("MIRAI_HOSTS", "")
    allowed |= {h.strip().lower().rstrip(".") for h in extra.split(",") if h.strip()}
    return host in allowed


def _gate_headers(handler) -> dict:
    """The gate's response headers, if it wants to send any (it sets the cookie when
    the token arrived through the ?k= link). Applied to the PAGE too: a phone that opens
    the one-tap link gets the dashboard AND the cookie that keeps it signed in."""
    gate = sys.modules.get("gate")
    if gate is None:
        return {}
    try:
        return dict(gate.response_headers(handler))
    except Exception:
        return {}


def _serve_spa(handler: BaseHTTPRequestHandler) -> None:
    """GET / and GET /index.html: the dashboard, gzipped when accepted."""
    path = _dashboard_file()
    if not path.exists():
        # Honest placeholder rather than a 404 the user reads as a broken build.
        body = (
            "<!doctype html><html><head><meta charset='utf-8'><title>MIRAI</title></head>"
            "<body style='font:15px/1.6 -apple-system,system-ui,sans-serif;max-width:40rem;margin:12vh auto;padding:0 1.5rem'>"
            "<h1 style='font-size:1.4rem'>MIRAI Mission Control — backend is up</h1>"
            "<p>The API is listening. The dashboard file was not found at "
            f"<code>{path}</code>.</p>"
            "<p>Put the dashboard HTML there (one file) and reload — no restart needed.</p>"
            "<p>Sanity check: <a href='/api/ping'>/api/ping</a> · "
            "<a href='/api/agents'>/api/agents</a> · "
            "<a href='/api/health'>/api/health</a></p>"
            "</body></html>"
        ).encode("utf-8")
        _send_bytes(handler, 200, body, "text/html; charset=utf-8", {}, head_only=handler.command == "HEAD")
        return

    etag = _etag_for(path)
    if handler.headers.get("If-None-Match") == etag:
        handler.send_response(304)
        handler.send_header("ETag", etag)
        for k, v in _gate_headers(handler).items():
            handler.send_header(k, v)
        handler.end_headers()
        return

    raw = path.read_bytes()
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    headers.update(_gate_headers(handler))
    accept = handler.headers.get("Accept-Encoding", "")
    if "gzip" in accept:
        body = gzip.compress(raw, 6)
        headers["Content-Encoding"] = "gzip"
    else:
        body = raw
    _send_bytes(handler, 200, body, "text/html; charset=utf-8", headers,
                head_only=handler.command == "HEAD", content_length=len(body))


# ---------------------------------------------------------------------------
# The one directory we serve: ~/mirai/lib — Hand mode's mediapipe models, which
# the page loads relative to itself. Read per request, like the page, and never
# outside its own folder.
# ---------------------------------------------------------------------------
LIB_TYPES = {
    ".mjs": "text/javascript; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".wasm": "application/wasm",
    ".task": "application/octet-stream",
    ".data": "application/octet-stream",
    ".json": "application/json; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
}


def _lib_file(rel: str) -> Path | None:
    """~mirai/lib/<rel>, or None if the path tries to leave the folder."""
    base = (MIRAI_DIR / "lib").resolve()
    target = (base / rel).resolve()
    if target != base and base not in target.parents:
        return None
    if not target.is_file():
        return None
    return target


def _serve_lib(handler: BaseHTTPRequestHandler, rel: str) -> None:
    path = _lib_file(rel)
    if path is None:
        body = json_bytes({"ok": False, "error": f"no such library file: {rel}"})
        _send_bytes(handler, 404, body, "application/json; charset=utf-8", {})
        return
    etag = _etag_for(path)
    if handler.headers.get("If-None-Match") == etag:
        handler.send_response(304)
        handler.send_header("ETag", etag)
        handler.end_headers()
        return
    raw = path.read_bytes()
    ctype = LIB_TYPES.get(path.suffix.lower(), "application/octet-stream")
    headers = {"ETag": etag, "Cache-Control": "public, max-age=3600"}
    body = raw
    if ctype.startswith("text/") and "gzip" in handler.headers.get("Accept-Encoding", ""):
        body = gzip.compress(raw, 6)
        headers["Content-Encoding"] = "gzip"
    _send_bytes(handler, 200, body, ctype, headers,
                head_only=handler.command == "HEAD", content_length=len(body))


def _send_bytes(handler, status: int, body: bytes, content_type: str,
                headers: dict, head_only: bool = False, content_length: int | None = None) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(content_length if content_length is not None else len(body)))
    for k, v in headers.items():
        handler.send_header(k, v)
    handler.end_headers()
    if not head_only:
        handler.wfile.write(body)


# ---------------------------------------------------------------------------
# Request handling
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "MIRAI/1.0"
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        # A client that lies about Content-Length must not be able to park a
        # worker thread for ever: every socket gets a read timeout.
        self.connection.settimeout(30)

    # -- helpers ----------------------------------------------------------
    def log_message(self, fmt, *args):      # quieter, and query strings redacted
        msg = fmt % args
        line = getattr(self, "path", "")
        if "?" in line:
            msg = msg.replace(line, line.split("?", 1)[0] + "?<redacted>")
        print(f"[api] {self.address_string()} {msg}")

    def _json(self, status: int, payload: dict) -> None:
        self._send_json(status, payload)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json_bytes(payload)
        _send_bytes(self, status, body, "application/json; charset=utf-8", _gate_headers(self))

    def _error(self, status: int, message: str) -> None:
        self._send_json(status, {"ok": False, "error": message})

    # -- routing ----------------------------------------------------------
    def handle_one_request(self):
        # A keep-alive connection that goes idle hits the read timeout here. That
        # is a closed tab, not an incident: close quietly instead of a traceback.
        try:
            super().handle_one_request()
        except (socket.timeout, TimeoutError, OSError):
            self.close_connection = True

    def do_GET(self):  self._dispatch("GET")
    def do_POST(self): self._dispatch("POST")
    def do_HEAD(self): self._dispatch("GET", head=True)
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Auth-Token, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def _dispatch(self, method: str, head: bool = False) -> None:
        parts = urlsplit(self.path)
        path = parts.path.rstrip("/") or "/"
        query = {k: v[0] for k, v in parse_qs(parts.query, keep_blank_values=True).items()}

        # Before anything is served: is the caller talking to us as a name we answer to?
        if not _host_ok(self.headers.get("Host")):
            self._error(403, "this server answers to 127.0.0.1, localhost and the names in "
                             "MIRAI_HOSTS only (a tailnet name belongs there)")
            return

        # Optional token gate (off unless MIRAI_AUTH=on). /api/ping is exempt.
        # This runs BEFORE the page and /lib below, on purpose: one server serves the
        # page and the API, so a gate that only covered /api/ would leave the dashboard
        # itself open to anyone who reaches the port -- and then the calls it makes from
        # the browser would carry the owner's own session anyway.
        try:
            gate = sys.modules.get("gate")
            if gate is not None and path != "/api/ping":
                gate.enforce(self)
        except ApiError as e:
            self._error(e.status, e.message)
            return
        except Exception as e:                       # gate.GateError has the same shape
            status = getattr(e, "status", None)
            if status:
                # A browser that asks for the PAGE gets a page. The API keeps answering
                # in JSON, because its callers are programs.
                if status == 401 and path in ("/", "/index.html") and method == "GET":
                    _send_bytes(self, 200, SIGNIN_PAGE.encode("utf-8"),
                                "text/html; charset=utf-8", {"Cache-Control": "no-store"})
                    return
                self._error(status, getattr(e, "message", str(e)))
                return
            raise

        # The one page this server will ever serve.
        if path in ("/", "/index.html") and method == "GET":
            _serve_spa(self)
            return

        # Hand mode loads its models relative to the page: /lib/mediapipe/...
        if path.startswith("/lib/") and method in ("GET", "HEAD"):
            _serve_lib(self, path[len("/lib/"):])
            return

        fn = ROUTES.get((method, path))
        if fn is None:
            if any(k[1] == path for k in ROUTES):
                allow = sorted({k[0] for k in ROUTES if k[1] == path})
                body = json_bytes({"ok": False, "error": f"{method} not allowed on {path}"})
                _send_bytes(self, 405, body, "application/json; charset=utf-8",
                            {"Allow": ", ".join(allow + ["OPTIONS"])})
            else:
                self._error(404, f"no route for {method} {path}")
            return

        body = None
        try:
            if method == "POST":
                body = self._read_body(path)
            result = fn(self, query, body)
        except ConnectionAbortedError:
            return                          # 413 already sent; the socket is closing
        except ApiError as e:
            self._error(e.status, e.message)
            return
        except BrokenPipeError:
            return
        except Exception:
            print(f"[api] 500 on {method} {path}")
            traceback.print_exc()
            self._error(500, "internal error (see the server log)")
            return

        try:
            if isinstance(result, Raw):
                _send_bytes(self, 200, result.body, result.content_type, dict(result.headers),
                            head_only=head)
            elif isinstance(result, Stream):
                self._stream(result, head_only=head)
            else:
                payload = result if isinstance(result, dict) else {"value": result}
                payload.setdefault("ok", True)
                self._send_json(200, payload)
        except BrokenPipeError:
            return

    def _read_body(self, path: str):
        length_hdr = self.headers.get("Content-Length")
        if length_hdr is None:
            return b"" if path in RAW_BODY_PATHS else None
        try:
            length = int(length_hdr)
        except ValueError:
            raise ApiError(400, "bad Content-Length")
        if length > MAX_BODY_BYTES:
            # Refuse BEFORE reading: reading 30 MB in order to refuse it is the
            # thing being defended against. Send the response, then close, so a
            # client that is still sending sees the 413 instead of a broken pipe.
            self.close_connection = True
            self._error(413, "body too large (30 MB limit)")
            raise ConnectionAbortedError
        raw = b""
        if length:
            try:
                remaining = length
                while remaining > 0:
                    chunk = self.rfile.read(min(remaining, 1 << 20))
                    if not chunk:
                        break
                    raw += chunk
                    remaining -= len(chunk)
            except (socket.timeout, TimeoutError):
                raise ApiError(400, "the body stopped arriving before Content-Length was met")
            if len(raw) < length:
                raise ApiError(400, "the body was shorter than Content-Length claimed")
        if path in RAW_BODY_PATHS:
            return raw
        if not raw:
            return {}
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except Exception:
            raise ApiError(400, "body is not valid JSON")
        if not isinstance(parsed, dict):
            raise ApiError(400, "body must be a JSON object")
        return parsed

    def _stream(self, stream: Stream, head_only: bool = False) -> None:
        self.send_response(200)
        self.send_header("Content-Type", stream.content_type)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        for k, v in stream.headers.items():
            self.send_header(k, v)
        self.end_headers()
        if head_only:
            return
        self.close_connection = True
        try:
            for chunk in stream.generator:
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT_DEFAULT
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    try:
        import store                     # creates our SQLite database on first use
        store.bootstrap()
    except Exception:
        print("[server] store failed to bootstrap:")
        traceback.print_exc()

    n = _load_modules()
    _register_fleet_route()
    _register_floor_routes()
    try:
        gate = __import__("gate")          # optional, present only if you built it
        gate.install()
    except ImportError:
        pass
    except Exception:
        traceback.print_exc()

    try:
        httpd = Server(("127.0.0.1", port), Handler)
    except OSError as e:
        print(f"[server] {port} is already in use ({e}). "
              f"Find the owner with: lsof -nP -iTCP:{port} -sTCP:LISTEN")
        return 1

    print(f"[server] MIRAI mission control on http://127.0.0.1:{port} "
          f"— {len(ROUTES)} routes registered, {n} modules loaded")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("[server] stopping")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
