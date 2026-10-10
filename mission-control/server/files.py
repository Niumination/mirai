"""files.py — their files: SOUL.md, config.yaml, USER.md, MEMORY.md, and skills.

Only a fixed list is exposed, and only these are ever writable. A backup is
taken before every save. A .yaml save that would not load is refused, because
the agent would not start afterwards.

Skills are the trap: a stock profile has dozens of them and hundreds of files
under that folder, nested one level down (skills/<category>/<skill>/). The
listing compares DIRECTORY NAMES AT DEPTH TWO against skills/.bundled_manifest;
what is not in the manifest is "not in the manifest", never "yours" — a skill
can ship without a manifest line and would then be credited to the operator on
every agent for ever.

The path gate is absolute: reject anything with .. before resolving, and confirm
the resolved path is inside that profile's folder and on the allowed list.
"""
from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

import store
from server import ApiError, Raw

MIRAI_DIR = Path(os.environ.get("MIRAI_DIR", str(Path.home() / "mirai"))).expanduser()
DATA_DIR = Path(os.environ.get("MIRAI_DATA_DIR", str(MIRAI_DIR / "data"))).expanduser()
BACKUP_DIR = DATA_DIR / "file-backups"
HERMES = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()

EDITABLE = {
    "SOUL.md": ("soul", "Who it is", "Its identity. The first line names it."),
    "config.yaml": ("config", "How it runs", "Model and settings. A broken YAML stops it starting."),
    "memories/USER.md": ("user", "Who it works for", "What the agent remembers about the operator."),
    "memories/MEMORY.md": ("memory", "What it remembers", "Long term memory, written by the agent."),
}
SENSITIVE = {"config.yaml", "memories/USER.md"}


def _profile_home(profile: str) -> Path:
    return HERMES if profile == "default" else HERMES / "profiles" / profile


def _profile_for_code(code: str) -> str:
    import roster
    profile = roster.profile_of_code(code)
    if not profile:
        raise ApiError(404, f"no agent with code {code}")
    return profile


def _check_rel(path: str) -> str:
    if ".." in path or path.startswith("/") or "\\" in path:
        raise ApiError(400, "bad path")
    if path not in EDITABLE:
        raise ApiError(400, f"only these files can be touched: {', '.join(EDITABLE)}")
    return path


def _resolve(profile: str, rel: str) -> Path:
    _check_rel(rel)
    home = _profile_home(profile).resolve()
    path = (home / rel).resolve()
    if home not in path.parents:
        raise ApiError(400, "path escapes the profile folder")
    return path


def _stat_file(path: Path, rel: str) -> dict | None:
    if not path.exists():
        return None
    st = path.stat()
    group = EDITABLE[rel]
    return {"name": Path(rel).name, "path": rel, "size": st.st_size, "mtime": st.st_mtime,
            "kind": group[0], "note": group[2], "sensitive": rel in SENSITIVE}


def _skills_summary(profile: str) -> dict:
    skills = _profile_home(profile) / "skills"
    if not skills.is_dir():
        return {"note": "no skills folder", "count": 0, "custom": 0}
    manifest = skills / ".bundled_manifest"
    shipped: set[str] = set()
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
            name = line.split(":", 1)[0].strip()
            if name:
                shipped.add(name)
    stock, custom = 0, []
    for category in sorted(p for p in skills.iterdir() if p.is_dir() and not p.name.startswith(".")):
        for skill in sorted(p for p in category.iterdir() if p.is_dir()):
            if skill.name in shipped:
                stock += 1
            else:
                custom.append(f"{category.name}/{skill.name}")
    return {"count": stock + len(custom), "stock": stock, "not_in_manifest": len(custom),
            "examples": custom[:8]}


def tree(req, query, body):                 # noqa: ANN001
    import roster
    agents_out = []
    for a in roster.agents()["agents"]:
        home = _profile_home(a["profile"])
        groups: dict[str, dict] = {}
        count = 0
        for rel, (gid, label, _note) in EDITABLE.items():
            item = _stat_file(home / rel, rel)
            if item is None:
                continue
            count += 1
            group = groups.setdefault(gid, {"id": gid, "label": label,
                                            "note": f"{label} — {home}",
                                            "files": []})
            group["files"].append(item)
        skills = _skills_summary(a["profile"])
        if skills.get("count"):
            gid = "skills"
            groups.setdefault(gid, {"id": gid, "label": "What it can do", "note": skills.get("note", ""),
                                    "files": [{"name": "skills", "path": "skills/", "size": 0,
                                               "mtime": 0, "kind": "skills",
                                               "note": (f"{skills['count']} skills · {skills['stock']} shipped · "
                                                        f"{skills['not_in_manifest']} not in the manifest"
                                                        if skills.get("stock") else f"{skills['count']} skills"),
                                               "sensitive": False}]})
        backups = len(list(BACKUP_DIR.glob(f"{a['profile']}/**/*"))) if BACKUP_DIR.exists() else 0
        agents_out.append({"code": a["code"], "short": a["short"], "name": a["name"],
                           "role": a["role"], "profile": a["profile"], "home": str(home),
                           "count": count, "custom": skills.get("not_in_manifest", 0),
                           "backups": backups,
                           "groups": list(groups.values())})
    return {"backups_total": sum(a["backups"] for a in agents_out),
            "backups_dir": str(BACKUP_DIR), "agents": agents_out}


def read_file(req, query, body):            # noqa: ANN001
    code = (query.get("agent") or "").upper()
    rel = query.get("path") or ""
    profile = _profile_for_code(code)
    path = _resolve(profile, rel)
    if not path.exists():
        raise ApiError(404, "the file does not exist yet")
    text = path.read_text(encoding="utf-8", errors="replace")
    item = _stat_file(path, rel)
    return {"agent": code, "path": rel, "text": text,
            "mtime": item["mtime"], "kind": item["kind"], "sensitive": item["sensitive"]}


def _validate_yaml(text: str) -> None:
    if not text.strip():
        raise ApiError(400, "an empty config.yaml would stop the agent starting — refused")
    if "\t" in text:
        raise ApiError(400, "tabs are not valid YAML indentation — use spaces")
    if not re.search(r"^[A-Za-z_][\w-]*\s*:", text, re.M):
        raise ApiError(400, "no `key:` line found — this is not YAML, refused")
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.split("#", 1)[0]
        if stripped.count("'") % 2 or stripped.count('"') % 2:
            raise ApiError(400, f"unclosed quote on line {i} — the agent would not load this")


def write_file(req, query, body):           # noqa: ANN001
    if body is None:
        body = {}
    code = str(body.get("agent") or "").upper()
    rel = str(body.get("path") or "")
    text = body.get("text")
    mtime = body.get("mtime")
    if not isinstance(text, str):
        raise ApiError(400, "text is required")
    profile = _profile_for_code(code)
    path = _resolve(profile, rel)
    if rel == "config.yaml":
        _validate_yaml(text)

    if path.exists():
        current = path.stat().st_mtime
        if mtime and abs(float(mtime) - current) > 1.0:
            raise ApiError(409, "the file changed on disk since you read it — read it again "
                                "before saving, so nothing is lost silently")
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = BACKUP_DIR / profile / f"{rel}.{stamp}"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

    if rel == "SOUL.md":
        os.utime(path, None)                # the agent's next turn starts a new session

    store.audit("operator", "files.write", {"profile": profile, "path": rel, "bytes": len(text)})
    item = _stat_file(path, rel)
    return {"agent": code, "path": rel, "mtime": item["mtime"], "saved": True}


def backups(req, query, body):              # noqa: ANN001
    code = (query.get("agent") or "").upper()
    rel = query.get("path") or ""
    profile = _profile_for_code(code)
    _check_rel(rel)
    folder = BACKUP_DIR / profile
    items = []
    if folder.exists():
        for p in sorted(folder.glob(f"{rel}.*"), key=lambda x: x.stat().st_mtime, reverse=True):
            items.append({"file": p.name, "size": p.stat().st_size, "mtime": p.stat().st_mtime})
    return {"agent": code, "path": rel, "backups": items[:50], "dir": str(folder)}


def register(route, ApiError_):        # noqa: ANN001
    """Declare this module's routes. Called once by server.py at load time."""
    route("GET", "/api/files/tree")(tree)
    route("GET", "/api/files/read")(read_file)
    route("POST", "/api/files/write")(write_file)
    route("GET", "/api/files/backups")(backups)
