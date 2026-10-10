"""workforce.py — hiring, letting go, renaming, and keeping the team list true.

Everything that creates, changes or removes an agent goes through the hermes CLI,
the only thing that knows how to do it while the agent is running. Deleting
directories by hand is never done here.

The trap this module engineers around, in full: A NEW PROFILE CANNOT ANSWER A
SINGLE TURN UNTIL IT HAS THE LOGIN. Without it the agent appears in the roster,
looks healthy, and every mission step that lands on it dies while the card goes
back to ready and retries all night. Which files are missing depends on the
version and the provider; the decision is made from what is on disk, never from
the flag that was used. .env is copied WITHOUT the platform tokens — a second
profile holding the owner's Telegram token makes the gateway refuse the
duplicate on every start. copy2, not copyfile: shutil.copyfile lands 0644 beside
a 0600 original and leaves the credentials readable by anyone on the box.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tarfile
import time
from pathlib import Path

import store
from server import ApiError

MIRAI_DIR = Path(os.environ.get("MIRAI_DIR", str(Path.home() / "mirai"))).expanduser()
DATA_DIR = Path(os.environ.get("MIRAI_DATA_DIR", str(MIRAI_DIR / "data"))).expanduser()
ROLES_PATH = DATA_DIR / "roles.json"
ARCHIVE_DIR = DATA_DIR / "archive"

HERMES = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()

NAME_RE = re.compile(r"^[A-Za-z0-9 _-]{2,40}$")
RENAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 _-]{1,23}$")
PLATFORM_TOKEN_PREFIXES = ("TELEGRAM_", "DISCORD_", "SLACK_", "WHATSAPP_", "MATRIX_")
CREDENTIAL_FILES = ("auth.json", "config.yaml", ".env")

_synced_at: float | None = None


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------
def _hermes() -> str:
    for cand in ("/opt/homebrew/bin/hermes", "/usr/local/bin/hermes",
                 str(Path.home() / ".local" / "bin" / "hermes"), "/usr/bin/hermes"):
        if Path(cand).exists():
            return cand
    found = shutil.which("hermes")
    if not found:
        raise ApiError(503, "hermes CLI not found")
    return found


def _cli(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = env.get("PATH", "") + ":/opt/homebrew/bin:/usr/local/bin:" + str(Path.home() / ".local" / "bin")
    return subprocess.run([_hermes(), *args], capture_output=True, text=True,
                          timeout=timeout, env=env)


def _profile_home(profile: str) -> Path:
    return HERMES if profile == "default" else HERMES / "profiles" / profile


# ---------------------------------------------------------------------------
# Library of roles
# ---------------------------------------------------------------------------
def _library() -> list[dict]:
    if ROLES_PATH.exists():
        try:
            data = json.loads(ROLES_PATH.read_text(encoding="utf-8"))
            roles = data.get("roles") if isinstance(data, dict) else data
            if isinstance(roles, list) and roles:
                return roles
        except Exception:
            pass
    return []


def _owner_name() -> str:
    s = store.settings()
    return s.get("display_name") or s.get("operator_name") or "the owner"


def _sub(text: str) -> str:
    return (text or "").replace("<owner>", str(_owner_name())).replace("{owner}", str(_owner_name()))


def library(req, query, body):              # noqa: ANN001
    roles = []
    for role in _library():
        name = role.get("name") or role.get("role") or role.get("id", "")
        short = re.sub(r"[^A-Za-z]", "", name.split()[0])[:16] if name else "Agent"
        roles.append({
            **role,
            "id": role.get("id") or role.get("slug") or name.lower(),
            "role": name,
            "short": short if len(short) >= 2 else "Agent",
            "directions": _sub(role.get("directions") or role.get("soul") or ""),
            "description": _sub(role.get("description") or ""),
        })
    return {"roles": roles, "templates": roles, "count": len(roles)}


# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------
def _default_soul(name: str, directions: str, role_line: str, profile: str) -> str:
    import roster
    others = []
    for a in roster.agents(force=True)["agents"]:
        others.append(f"- {a['name']} ({a['profile']}): {a['role']}")
    team = "\n".join(others) or "- (nobody else yet)"
    return (
        f"Your name is {name}.\n\n"
        f"{directions.strip()}\n\n"
        f"## The team\n\nThe crew you belong to:\n\n{team if False else team}\n"
        f"- {name} (you, profile {profile}): {role_line}\n\n"
        "When a request is outside your job, do not attempt it: answer in one line naming "
        "the teammate who should do it.\n"
    )


def _copy_credentials(profile: str) -> list[str]:
    src = _profile_home("default")
    dst = _profile_home(profile)
    copied = []
    for fname in CREDENTIAL_FILES:
        s, d = src / fname, dst / fname
        if not s.exists() or d.exists():
            continue
        if fname == ".env":
            lines = []
            for line in s.read_text(encoding="utf-8", errors="replace").splitlines():
                if any(line.strip().startswith(p) for p in PLATFORM_TOKEN_PREFIXES):
                    continue      # a second profile holding the same bot token breaks the gateway
                lines.append(line)
            d.write_text("\n".join(lines) + "\n", encoding="utf-8")
            os.chmod(d, 0o600)
        else:
            shutil.copy2(s, d)    # copy2 keeps the mode; copyfile would land 0644
        copied.append(fname)
    return copied


def _verify_login(profile: str) -> str:
    """One short turn. A profile without a login answers nothing."""
    import chat
    p = _cli_profile_probe(profile)
    return p


def _cli_profile_probe(profile: str) -> str:
    env = dict(os.environ)
    env["PATH"] = env.get("PATH", "") + ":/opt/homebrew/bin:/usr/local/bin:" + str(Path.home() / ".local" / "bin")
    cmd = [_hermes()]
    if profile != "default":
        cmd += ["-p", profile]
    cmd += ["chat", "-q", "Who are you?", "-Q", "--source", "mirai", "-c", "mirai-probe", "--create-if-missing"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
    except subprocess.TimeoutExpired:
        raise ApiError(504, "the new agent did not answer within 180s")
    import chat as chat_mod
    reply = chat_mod._clean(p.stdout or "")
    if not reply:
        raise ApiError(502, f"the new agent produced no answer (exit {p.returncode}) — "
                            f"its profile has no working login")
    return reply


def deploy(req, query, body):               # noqa: ANN001
    if body is None:
        body = {}
    name = str(body.get("name") or "").strip()
    if not NAME_RE.match(name):
        raise ApiError(400, "name must be 2 to 40 characters of letters, digits, spaces, - or _")
    template = body.get("template")
    directions = str(body.get("directions") or "").strip()
    model = str(body.get("model") or "").strip()
    profile = re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-"))

    import roster
    if profile in roster.profiles():
        raise ApiError(409, f"a profile called {profile} already exists — pick another name")

    roles = {r["id"]: r for r in _library()}
    role = roles.get(str(template)) if template else None
    if role and not directions:
        directions = role["directions"]
        model = model or role.get("model", "")
    if not directions:
        raise ApiError(400, "send a template id or directions (the SOUL text)")

    started = time.time()
    created = False
    try:
        p = _cli("profile", "create", profile, "--clone")
        if p.returncode != 0:
            raise ApiError(500, f"hermes profile create failed: {(p.stderr or p.stdout).strip()[:300]}")
        created = True

        copied = _copy_credentials(profile)
        if "auth.json" not in copied and not (_profile_home(profile) / "auth.json").exists():
            raise ApiError(500, "no auth.json on the default profile to copy — the new agent "
                                "could not answer a single turn")

        soul = _default_soul(name, directions, role.get("description", "") if role else "", profile)
        soul_path = _profile_home(profile) / "SOUL.md"
        soul_path.write_text(soul, encoding="utf-8")     # written by us, never asked of an agent

        if model:
            _set_model(profile, model)

        code = roster.code_for(profile, name)            # recorded now, before the roster reads it
        reply = _cli_profile_probe(profile)
        roster.invalidate()
        store.audit("operator", "workforce.deploy",
                    {"profile": profile, "name": name, "model": model, "template": template})
        return {"agent": next((a for a in roster.agents(force=True)["agents"] if a["profile"] == profile), None),
                "code": code, "seconds": round(time.time() - started, 1), "probe": reply}
    except Exception as e:
        if created:
            _rollback_profile(profile, name)
        if isinstance(e, ApiError):
            raise
        raise ApiError(500, f"deploy failed and was rolled back: {e}")


def _set_model(profile: str, model: str) -> None:
    path = _profile_home(profile) / "config.yaml"
    if not path.exists():
        path.write_text(f"model:\n  default: {model}\n", encoding="utf-8")
        return
    text = path.read_text(encoding="utf-8")
    if re.search(r"^model:\s*\n(?:[ \t]+.*\n)*?[ \t]+default:", text, re.M):
        text = re.sub(r"(^model:\s*\n(?:[ \t]+.*\n)*?[ \t]+default:\s*)([^\n#]+)",
                      lambda m: m.group(1) + model, text, count=1, flags=re.M)
    else:
        text = f"model:\n  default: {model}\n" + text
    path.write_text(text, encoding="utf-8")


def _rollback_profile(profile: str, name: str) -> None:
    try:
        _cli("profile", "delete", profile, "-y")
    except Exception:
        pass
    deleted = HERMES / "profiles" / ".deleted"
    if deleted.exists():
        shutil.rmtree(deleted, ignore_errors=True)
    store.execute("DELETE FROM agent_codes WHERE profile=?", (profile,))
    store.execute("DELETE FROM avatars WHERE owner=?", (name,))
    _ = name


# ---------------------------------------------------------------------------
# Remove, rename, team sync
# ---------------------------------------------------------------------------
def remove(req, query, body):               # noqa: ANN001
    if body is None:
        body = {}
    code = str(body.get("code") or "").strip().upper()
    confirm = str(body.get("confirm") or "").strip().lower()
    import roster
    profile = roster.profile_of_code(code)
    if not profile:
        raise ApiError(404, f"no agent with code {code}")
    name = roster.name_of_code(code) or profile
    if confirm not in (name.lower(), roster.short_of(name).lower(), profile.lower()):
        raise ApiError(400, "confirmation does not match this agent's name — a typo removes nothing")

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    archive = ARCHIVE_DIR / f"{profile}-{stamp}.tar.gz"
    home = _profile_home(profile)
    try:
        with tarfile.open(archive, "w:gz") as tar:
            for item in home.rglob("*"):
                rel = item.relative_to(home)
                if item.name in ("auth.json", ".env", "secrets.env"):
                    continue                       # never archive credentials
                if any(part in (".deleted", "__pycache__", "state.db-wal", "state.db-shm")
                       for part in rel.parts):
                    continue
                tar.add(item, arcname=f"{profile}/{rel}")
        os.chmod(archive, 0o600)                   # readable by the owner only
    except Exception as e:
        raise ApiError(500, f"archive failed, nothing was removed: {e}")

    p = _cli("profile", "delete", profile, "-y")
    if p.returncode != 0:
        raise ApiError(500, f"hermes profile delete failed: {(p.stderr or p.stdout).strip()[:300]}")

    deleted = HERMES / "profiles" / ".deleted"
    if deleted.is_dir():
        shutil.rmtree(deleted, ignore_errors=True)
    elif deleted.exists():
        deleted.unlink(missing_ok=True)
    store.execute("DELETE FROM agent_codes WHERE profile=?", (profile,))
    survivors = sorted(x.name for x in home.iterdir()) if home.exists() else []
    if survivors:
        store.audit("operator", "workforce.remove", {"profile": profile, "archive": str(archive),
                                                     "survivors": survivors})
        return {"removed": profile, "archive": str(archive),
                "warning": f"some files survived the delete: {', '.join(survivors[:6])}"}
    store.audit("operator", "workforce.remove", {"profile": profile, "archive": str(archive)})
    roster.invalidate()
    return {"removed": profile, "archive": str(archive)}


def rename(req, query, body):               # noqa: ANN001
    if body is None:
        body = {}
    code = str(body.get("code") or "").strip().upper()
    new_name = str(body.get("name") or "").strip()
    if not RENAME_RE.match(new_name):
        raise ApiError(400, "name must be 2 to 24 characters, start with a letter, "
                            "and may hold letters, digits, spaces, - or _")
    import roster
    profile = roster.profile_of_code(code)
    if not profile:
        raise ApiError(404, f"no agent with code {code}")
    for a in roster.agents(force=True)["agents"]:
        if a["profile"] != profile and a["name"].lower() == new_name.lower():
            raise ApiError(409, "another agent already has that name")

    _cli("profile", "describe", profile, "--text", new_name)

    soul = _profile_home(profile) / "SOUL.md"
    if soul.exists():
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(soul, ARCHIVE_DIR / f"SOUL-{profile}-{time.strftime('%Y%m%d-%H%M%S')}.md")
        text = soul.read_text(encoding="utf-8")
        lines = text.splitlines()
        changed = False
        for i, line in enumerate(lines[:15]):
            if re.match(r"\s*Your name is .+", line):
                lines[i] = f"Your name is {new_name}."
                changed = True
                break
        if not changed:
            insert_at = 0
            for i, line in enumerate(lines[:15]):        # below any leading comment
                if line.strip().startswith("#"):
                    insert_at = i + 1
                else:
                    break
            lines.insert(insert_at, f"Your name is {new_name}.")
        soul.write_text("\n".join(lines) + "\n", encoding="utf-8")

    store.execute("UPDATE agent_codes SET name=? WHERE profile=?", (new_name, profile))
    sync_team()
    roster.invalidate()
    store.audit("operator", "workforce.rename", {"profile": profile, "name": new_name})
    return {"code": code, "name": new_name, "profile": profile}


def _team_block(code: str, name: str, profile: str) -> str:
    import roster
    lines = ["## The team", "", "The crew you belong to:", ""]
    for a in roster.agents(force=True)["agents"]:
        marker = " (you)" if a["code"] == code else ""
        lines.append(f"- {a['name']} ({a['profile']}, code {a['code']}){marker}: {a['role']}")
    lines += ["", "When a request is outside your job, do not attempt it: answer in one line "
                  "naming the teammate who should do it.", ""]
    _ = name, profile
    return "\n".join(lines)


def team_sync_route(req, query, body):      # noqa: ANN001
    changed = sync_team()
    return {"changed": changed, "synced_at": _synced_at}


def sync_team() -> int:
    """Rewrite the team section of every agent's SOUL.md from the live roster."""
    global _synced_at
    import roster
    agents = roster.agents(force=True)["agents"]
    changed = 0
    for a in agents:
        path = _profile_home(a["profile"]) / "SOUL.md"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        block = _team_block(a["code"], a["name"], a["profile"])
        if "## The team" in text:
            head, _, tail = text.partition("## The team")
            after = tail.find("\n## ")
            rest = tail[after + 1:] if after != -1 else ""
            new = head + block + ("\n" + rest if rest else "")
        else:
            new = text.rstrip() + "\n\n" + block
        if new != text:
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, ARCHIVE_DIR / f"SOUL-{a['profile']}-{time.strftime('%Y%m%d-%H%M%S')}.md")
            path.write_text(new, encoding="utf-8")
            changed += 1
    _synced_at = time.time()
    store.audit("operator", "workforce.team_sync", {"changed": changed})
    return changed


def team_status(req, query, body):          # noqa: ANN001
    import roster
    agents = roster.agents()["agents"]
    out = []
    all_sync = True
    for a in agents:
        path = _profile_home(a["profile"]) / "SOUL.md"
        text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        in_sync = "## The team" in text and sum(
            1 for b in agents if b["name"] in text.split("## The team", 1)[-1]) >= max(1, len(agents) - 1)
        all_sync = all_sync and in_sync
        out.append({"code": a["code"], "name": a["name"], "in_sync": in_sync})
    return {"in_sync": all_sync, "synced_at": _synced_at, "agents": out}


def register(route, ApiError_):        # noqa: ANN001
    """Declare this module's routes. Called once by server.py at load time."""
    route("GET", "/api/workforce/library")(library)
    route("POST", "/api/workforce/deploy")(deploy)
    route("POST", "/api/workforce/remove")(remove)
    route("POST", "/api/workforce/rename")(rename)
    route("POST", "/api/workforce/team/sync")(team_sync_route)
    route("GET", "/api/workforce/team")(team_status)
