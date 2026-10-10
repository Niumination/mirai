"""gate.py — the optional lock on the door (off by default).

One server serves the page and the API, so there is no proxy in the middle and
nothing to forward: the gate simply applies to both, which the two-process shape
could not do. An unauthenticated browser gets our JSON 401, not the dashboard.

Off unless MIRAI_AUTH=on. The token is read from an environment variable or a
file with 0600 permissions, never from the database and never printed to a log.
/api/ping is exempt, so an uptime check does not go red the moment the gate goes
on.

One detail that undoes everything above if missed: the base handler logs the
request line verbatim, so a ?k=<token> link would write the token in plain text
into the log for ever. server.py redacts the query string for exactly this
reason — keep it that way if you edit it.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from http.cookies import SimpleCookie
from pathlib import Path

MIRAI_DIR = Path(os.environ.get("MIRAI_DIR", str(Path.home() / "mirai"))).expanduser()
DATA_DIR = Path(os.environ.get("MIRAI_DATA_DIR", str(MIRAI_DIR / "data"))).expanduser()
TOKEN_FILE = DATA_DIR / "auth.token"
COOKIE = "mirai_auth"
ENABLED = os.environ.get("MIRAI_AUTH", "").lower() in ("on", "1", "true", "yes")


class GateError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message


def token() -> str | None:
    env = os.environ.get("MIRAI_TOKEN")
    if env:
        return env.strip()
    if TOKEN_FILE.exists():
        try:
            return TOKEN_FILE.read_text().strip()
        except OSError:
            return None
    return None


def ensure_token() -> str:
    """Generate the token on first use; 0600, never served."""
    t = token()
    if t:
        return t
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    t = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(t + "\n", encoding="utf-8")
    os.chmod(TOKEN_FILE, 0o600)
    return t


def install() -> None:
    if ENABLED and not token():
        t = ensure_token()
        print(f"[gate] MIRAI_AUTH is on and no token existed. Token written to {TOKEN_FILE} "
              f"(0600). Show its link with: ~/mirai/link.sh")
        _ = t


def _provided(req) -> tuple[str | None, bool]:
    hdr = req.headers.get("X-Auth-Token")
    if hdr:
        return hdr.strip(), False
    auth = req.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip(), False
    cookie = req.headers.get("Cookie")
    if cookie:
        try:
            jar = SimpleCookie()
            jar.load(cookie)
            if COOKIE in jar:
                return jar[COOKIE].value, True
        except Exception:
            pass
    query = req.path.split("?", 1)[1] if "?" in req.path else ""
    for pair in query.split("&"):
        k, _, v = pair.partition("=")
        if k == "k" and v:
            return v, False
    return None, False


def enforce(req) -> None:
    if not ENABLED:
        return
    expected = token()
    if not expected:
        raise GateError(503, "the gate is on but no token is configured")
    provided, _from_cookie = _provided(req)
    if provided and hmac.compare_digest(provided, expected):
        req._mirai_authenticated = True
        return
    raise GateError(401, "authentication required")


def response_headers(req) -> dict:
    """Set the cookie when the token arrived through the ?k= link, so opening it
    on a phone is one tap rather than typing a token."""
    provided, from_cookie = _provided(req)
    if not ENABLED or from_cookie or not provided:
        return {}
    if not hmac.compare_digest(provided, token() or ""):
        return {}
    digest = hashlib.sha256(provided.encode()).hexdigest()[:16]
    return {"Set-Cookie": f"{COOKIE}={provided}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000",
            "X-Mirai-Session": digest}
