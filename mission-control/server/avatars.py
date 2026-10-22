"""avatars.py — faces for the crew and for the operator.

Three jobs in one route, because the dashboard always sends an `owner` (an agent
code, or the string "operator") plus exactly one of library / upload / reset:

    {owner, library: "<name>"}     wear one the page offered
    {owner, upload: "data:image/png;base64,..."}
    {owner, reset: true}           back to the default

There is no separate upload route and no enumeration of the shipped catalogue:
the fifty-two portraits live INSIDE the dashboard file, which this server cannot
see into, so a fabricated id would be a broken picture on every page that draws
it. GET /api/avatars/library exists for portraits the operator adds later.

A saved choice only reaches a page through the roster record (prompt 13):
nothing reads this module directly. A picture that saves and never appears is
the failure to expect here.
"""
from __future__ import annotations

import base64
import os
import re
import time
import uuid
from pathlib import Path

import store
from server import ApiError, Raw

MIRAI_DIR = Path(os.environ.get("MIRAI_DIR", str(Path.home() / "mirai"))).expanduser()
DATA_DIR = Path(os.environ.get("MIRAI_DATA_DIR", str(MIRAI_DIR / "data"))).expanduser()
AVATARS_DIR = DATA_DIR / "avatars"
PACK_DIR = Path(__file__).resolve().parent.parent / "web" / "avatars"

MAX_BYTES = 4 * 1024 * 1024

MAGIC = (
    (b"\x89PNG\r\n\x1a\n", ".png", "image/png"),
    (b"\xff\xd8\xff", ".jpg", "image/jpeg"),
)


def _sniff(blob: bytes) -> tuple[str, str] | None:
    """Checked by reading the first bytes, never by trusting the file name."""
    for magic, ext, ctype in MAGIC:
        if blob.startswith(magic):
            return ext, ctype
    if len(blob) > 12 and blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return ".webp", "image/webp"
    return None


def _decode_data_url(data: str) -> bytes:
    if not isinstance(data, str) or "," not in data:
        raise ApiError(400, "upload must be a data: URL")
    head, payload = data.split(",", 1)
    if ";base64" not in head:
        raise ApiError(400, "upload must be base64 encoded")
    try:
        blob = base64.b64decode(payload)
    except Exception:
        raise ApiError(400, "upload is not valid base64")
    if len(blob) > MAX_BYTES:
        raise ApiError(413, "image is over the 4 MB limit")
    return blob


def pack_for(code: str):
    """Shipped bust: webp first, then png. TR → tr.webp / tr.png."""
    if not code:
        return None
    stem = str(code).strip().lower()[:2]
    if not re.match(r"^[a-z]{2}$", stem):
        return None
    if not (PACK_DIR / f"{stem}.webp").is_file() and not (PACK_DIR / f"{stem}.png").is_file():
        return None
    url = f"/api/avatars/pack?code={stem}"
    still_path = PACK_DIR / f"{stem}-still.webp"
    still = f"{url}&still=1" if still_path.is_file() else url
    return {"id": stem, "url": url, "still": still, "thumb": url, "kind": "pack"}


def library(req, query, body):              # noqa: ANN001
    """Only portraits WE have added. The shipped catalogue is inside the page."""
    items = []
    if AVATARS_DIR.exists():
        for p in sorted(AVATARS_DIR.iterdir()):
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                items.append({"id": p.name, "url": f"/api/avatars/file?name={p.name}",
                              "kind": "upload", "name": p.stem})
    return {"sections": [], "portraits": items}


def operator(req, query, body):             # noqa: ANN001
    import settings as settings_mod
    row = store.one("SELECT * FROM avatars WHERE owner='operator'")
    avatar = None
    if row and row["kind"] == "upload" and row["file_name"]:
        avatar = {"id": row["file_name"], "url": f"/api/avatars/file?name={row['file_name']}",
                  "thumb": f"/api/avatars/file?name={row['file_name']}", "kind": "upload"}
    elif row and row["kind"] == "library":
        avatar = {"id": row["library_id"], "kind": "library"}
    s = settings_mod._current()
    return {"avatar": avatar, "name": s.get("display_name") or s.get("operator_name") or ""}


def set_avatar(req, query, body):           # noqa: ANN001
    if body is None:
        body = {}
    owner = str(body.get("owner") or "").strip()
    if not owner:
        raise ApiError(400, "owner is required (an agent code, or 'operator')")

    if body.get("reset"):
        store.execute("DELETE FROM avatars WHERE owner=?", (owner,))
        store.audit("operator", "avatar.reset", {"owner": owner})
        return {"owner": owner, "avatar": None}

    if isinstance(body.get("upload"), str):
        blob = _decode_data_url(body["upload"])
        sniffed = _sniff(blob)
        if sniffed is None:
            raise ApiError(400, "only png, jpg and webp images are accepted "
                                "(checked by content, not by file name)")
        ext, _ctype = sniffed
        AVATARS_DIR.mkdir(parents=True, exist_ok=True)
        fname = uuid.uuid4().hex + ext
        (AVATARS_DIR / fname).write_bytes(blob)
        store.execute(
            "INSERT OR REPLACE INTO avatars(owner, kind, file_name, library_id, updated_at) "
            "VALUES(?,?,?,?,?)", (owner, "upload", fname, None, time.time()))
        store.audit("operator", "avatar.upload", {"owner": owner, "file": fname, "bytes": len(blob)})
        return {"owner": owner, "avatar": {"id": fname, "kind": "upload",
                                           "url": f"/api/avatars/file?name={fname}"}}

    if isinstance(body.get("library"), str) and body["library"]:
        lib = body["library"]
        # The catalogue is inside the dashboard file, so the name cannot be
        # checked against a list: stored as given, resolved by the page.
        store.execute(
            "INSERT OR REPLACE INTO avatars(owner, kind, file_name, library_id, updated_at) "
            "VALUES(?,?,?,?,?)", (owner, "library", None, lib, time.time()))
        store.audit("operator", "avatar.library", {"owner": owner, "id": lib})
        import roster
        roster.invalidate()
        return {"owner": owner, "avatar": {"id": lib, "kind": "library"}}

    raise ApiError(400, "send library, upload or reset")


def get_file(req, query, body):             # noqa: ANN001
    name = query.get("name") or ""
    if not re.match(r"^[0-9a-f]{32}(\.(png|jpg|jpeg|webp))?$", name):
        raise ApiError(400, "bad avatar file name")
    path = (AVATARS_DIR / name).resolve()
    if AVATARS_DIR.resolve() not in path.parents or not path.exists():
        raise ApiError(404, "no such avatar")
    ctype = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".webp": "image/webp"}.get(path.suffix.lower(), "application/octet-stream")
    return Raw(path.read_bytes(), ctype, {"Cache-Control": "private, max-age=600"})


def get_pack(req, query, body):             # noqa: ANN001
    code = (query.get("code") or "").lower()
    if not re.match(r"^[a-z]{2}$", code):
        raise ApiError(400, "bad pack code")
    root = PACK_DIR.resolve()
    want_still = str(query.get("still") or "") in ("1", "true", "yes")
    names = []
    if want_still:
        names.append(f"{code}-still.webp")
    names.extend([f"{code}.webp", f"{code}.png"])
    ctype_map = {".webp": "image/webp", ".png": "image/png"}
    for name in names:
        path = (PACK_DIR / name).resolve()
        if path.parent != root or not path.is_file():
            continue
        ctype = ctype_map.get(path.suffix.lower(), "application/octet-stream")
        return Raw(path.read_bytes(), ctype, {"Cache-Control": "public, max-age=86400"})
    raise ApiError(404, "no pack portrait")


def register(route, ApiError_):        # noqa: ANN001
    """Declare this module's routes. Called once by server.py at load time."""
    route("GET", "/api/avatars/library")(library)
    route("GET", "/api/avatars/operator")(operator)
    route("POST", "/api/avatars/set")(set_avatar)
    route("GET", "/api/avatars/file")(get_file)
    route("GET", "/api/avatars/pack")(get_pack)
