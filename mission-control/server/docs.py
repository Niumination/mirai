"""docs.py — the Library: markdown documents the fleet writes and the owner reads.

Layout: ~/mirai/data/docs/<agent code>/<date>_<slug>.md

Each document opens with a small front matter block. Parsing is lenient: a file
somebody edited by hand is still a document.

The id is the path relative to the docs folder, resolved and confirmed inside it
before anything is opened — a token-free read route must never become an
arbitrary-file read.
"""
from __future__ import annotations

import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import store
from server import ApiError, Raw

MIRAI_DIR = Path(os.environ.get("MIRAI_DIR", str(Path.home() / "mirai"))).expanduser()
DATA_DIR = Path(os.environ.get("MIRAI_DATA_DIR", str(MIRAI_DIR / "data"))).expanduser()
DOCS_DIR = DATA_DIR / "docs"
DELETED_DIR = DATA_DIR / "docs-deleted"

STATUSES = ("Saved", "From chat", "In review", "Delivered")
EXCERPT_BYTES = 1400


def _resolve(doc_id: str) -> Path:
    if not doc_id or ".." in doc_id or doc_id.startswith("/"):
        raise ApiError(400, "bad document id")
    path = (DOCS_DIR / doc_id).resolve()
    if DOCS_DIR.resolve() not in path.parents or not path.is_file():
        raise ApiError(404, "no such document")
    return path


def _front_matter(text: str) -> dict:
    meta = {"title": "", "agent": "", "mission": "", "status": "", "created": "", "updated": ""}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            block = text[3:end]
            for line in block.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
    return meta


def _body(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def _excerpt_and_words(path: Path) -> tuple[str, int, bool]:
    """First 1400 bytes for the excerpt. Only read the rest for the word count —
    guessing from the byte size was out by a factor of two in testing."""
    with path.open("rb") as fh:
        head = fh.read(EXCERPT_BYTES)
        rest = fh.read()
    text = head.decode("utf-8", errors="replace")
    body = _body(text)
    excerpt = " ".join(re.sub(r"^#.*$", "", body, flags=re.M).split())[:220]
    words = len(re.findall(r"\S+", body)) if not rest else None
    if words is None:
        full = (text + rest.decode("utf-8", errors="replace"))
        words = len(re.findall(r"\S+", _body(full)))
    return excerpt, words, True


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "document"


def list_docs(req, query, body):            # noqa: ANN001
    items = []
    if DOCS_DIR.exists():
        for path in sorted(DOCS_DIR.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            if "_deleted" in path.parts:
                continue
            rel = str(path.relative_to(DOCS_DIR))
            try:
                excerpt, words, _ = _excerpt_and_words(path)
                meta = _front_matter(path.read_text(encoding="utf-8", errors="replace")[:2000])
            except OSError:
                continue
            st = path.stat()
            items.append({
                "id": rel,
                "agent": (meta.get("agent") or rel.split("/")[0]).upper(),
                "title": meta.get("title") or path.stem.replace("-", " "),
                "status": meta.get("status") or "Saved",
                "mission": meta.get("mission") or "",
                "created": meta.get("created") or datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d"),
                "updated": meta.get("updated") or datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d"),
                "excerpt": excerpt,
                "words": words,
                "mtime": st.st_mtime,
            })
    return {"documents": items, "count": len(items), "dir": str(DOCS_DIR)}


def read_doc(req, query, body):             # noqa: ANN001
    path = _resolve(query.get("id") or "")
    text = path.read_text(encoding="utf-8", errors="replace")
    return {"id": query["id"], "text": text, "meta": _front_matter(text)}


def download_doc(req, query, body):         # noqa: ANN001
    path = _resolve(query.get("id") or "")
    nice = path.name
    return Raw(path.read_bytes(), "text/markdown; charset=utf-8",
               {"Content-Disposition": f'attachment; filename="{quote(nice)}"'})


def save_doc(req, query, body):             # noqa: ANN001
    if body is None:
        body = {}
    title = str(body.get("title") or "").strip()
    text = str(body.get("text") or "")
    if not title:
        raise ApiError(400, "title is required")
    agent = str(body.get("agent") or "").strip().upper() or "YOU"
    status = body.get("status")
    if status is not None and status not in STATUSES:
        raise ApiError(400, f"status must be one of: {', '.join(STATUSES)}")

    doc_id = body.get("id")
    today = datetime.now().strftime("%Y-%m-%d")
    if doc_id:
        path = _resolve(str(doc_id))
        meta = _front_matter(path.read_text(encoding="utf-8", errors="replace"))
        created = meta.get("created") or today
        keep_status = meta.get("status") or "Saved"
        agent = meta.get("agent") or agent
        mission = meta.get("mission") or ""
    else:
        folder = DOCS_DIR / agent
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{today}_{_slug(title)}.md"
        n = 1
        while path.exists():
            n += 1
            path = folder / f"{today}_{_slug(title)}-{n}.md"
        created, keep_status, mission = today, "Saved", ""

    front = (f"---\ntitle: {title}\nagent: {agent}\nmission: {mission}\n"
             f"status: {status or keep_status}\ncreated: {created}\n"
             f"updated: {today}\n---\n\n")
    path.write_text(front + text, encoding="utf-8")
    store.audit("operator", "docs.save", {"id": str(path.relative_to(DOCS_DIR)), "new": not doc_id})
    return {"id": str(path.relative_to(DOCS_DIR)), "path": str(path)}


def delete_doc(req, query, body):           # noqa: ANN001
    if body is None:
        body = {}
    doc_id = str(body.get("id") or "")
    path = _resolve(doc_id)
    DELETED_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = DELETED_DIR / f"{stamp}_{path.name}"
    shutil.move(str(path), str(target))
    store.audit("operator", "docs.delete", {"id": doc_id, "copy": str(target)})
    return {"deleted": doc_id, "copy": str(target)}


def from_chat(req, query, body):            # noqa: ANN001
    if body is None:
        body = {}
    text = str(body.get("text") or "").strip()
    agent = str(body.get("agent") or "").strip().upper()
    if not text:
        raise ApiError(400, "text is required")
    if not agent:
        raise ApiError(400, "agent is required")
    title = str(body.get("title") or "").strip() or f"From {agent} — {datetime.now().strftime('%d %b %H:%M')}"
    return save_doc(req, query, {"title": title, "text": text, "agent": agent, "status": "From chat"})


def register(route, ApiError_):        # noqa: ANN001
    """Declare this module's routes. Called once by server.py at load time."""
    route("GET", "/api/docs")(list_docs)
    route("GET", "/api/docs/read")(read_doc)
    route("GET", "/api/docs/download")(download_doc)
    route("POST", "/api/docs/save")(save_doc)
    route("POST", "/api/docs/delete")(delete_doc)
    route("POST", "/api/docs/from-chat")(from_chat)
