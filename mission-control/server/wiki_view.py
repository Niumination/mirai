"""wiki_view.py — read-only window onto the Niumination wiki.

Does not run wiki verbs. Does not write. Path from roster._wiki_dir()
(CREW_WIKI_DIR → Desktop/Niumination/wiki → ~/wiki).
"""
from __future__ import annotations

import os
from pathlib import Path

import roster
from server import ApiError

MAX_FILES = 200
MAX_BYTES = 400_000
SKIP_DIR = {".git", ".obsidian", "node_modules", "_working"}


def _root() -> Path:
    return roster._wiki_dir().expanduser().resolve()


def _safe(rel: str) -> Path:
    if not rel or ".." in rel or rel.startswith("/") or "\\" in rel:
        raise ApiError(400, "bad wiki path")
    if not rel.endswith(".md"):
        raise ApiError(400, "only markdown")
    root = _root()
    if not root.is_dir():
        raise ApiError(404, "wiki folder not found")
    path = (root / rel).resolve()
    if root not in path.parents and path != root:
        raise ApiError(400, "path escapes wiki")
    return path


def listing(_req, _query, _body):  # noqa: ANN001
    root = _root()
    items = []
    if root.is_dir():
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR and not d.startswith(".")]
            for name in filenames:
                if not name.endswith(".md"):
                    continue
                p = Path(dirpath) / name
                rel = str(p.relative_to(root)).replace("\\", "/")
                try:
                    st = p.stat()
                except OSError:
                    continue
                items.append({"id": rel, "name": name, "path": rel, "size": st.st_size, "mtime": st.st_mtime})
                if len(items) >= MAX_FILES:
                    break
            if len(items) >= MAX_FILES:
                break
    items.sort(key=lambda x: x["path"])
    return {
        "path": str(root),
        "exists": root.is_dir(),
        "documents": items,
        "read_only": True,
    }


def page(_req, query, _body):  # noqa: ANN001
    rel = str(query.get("id") or query.get("name") or "").strip()
    path = _safe(rel)
    if not path.is_file():
        raise ApiError(404, "no such page")
    if path.stat().st_size > MAX_BYTES:
        raise ApiError(413, "page too large to show here")
    text = path.read_text(encoding="utf-8", errors="replace")
    return {"id": rel, "path": rel, "text": text, "read_only": True}


def register(route, ApiError_):  # noqa: ANN001
    route("GET", "/api/wiki")(listing)
    route("GET", "/api/wiki/page")(page)
