"""models.py — which models the crew can run, asked of Hermes itself.

Never a hardcoded list: a model the provider adds must appear by itself. The
provider list is read from the crew's own config.yaml files, then each provider
is queried through Hermes' own Python (hermes_cli.models.provider_model_ids),
cached ten minutes so a page reload is not an API call.

POST /api/models/assign writes model.default in that agent's config.yaml through
the same backed-up write as files.py, and refuses a model its provider does not
offer.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import store
from server import ApiError

HERMES = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
CACHE_TTL = 600
_cache: dict = {"at": 0.0, "value": None}


def _profile_home(profile: str) -> Path:
    return HERMES if profile == "default" else HERMES / "profiles" / profile


def _provider_of(profile: str) -> str:
    """The provider this profile's config names, scanned rather than parsed."""
    text = ""
    try:
        text = (_profile_home(profile) / "config.yaml").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    m = re.search(r"^\s*provider:\s*([^\n#]+)", text, re.M)
    if m:
        return m.group(1).strip().strip('"').strip("'")
    m = re.search(r"^\s*provider:\s*$", text, re.M)
    if m:
        m2 = re.search(r"^\s*provider:\s*\n(?:[ \t]+.*\n)*?[ \t]+default:\s*([^\n#]+)", text, re.M)
        if m2:
            return m2.group(1).strip().strip('"').strip("'")
    # model ids are usually namespaced: provider/model
    m = re.search(r"^\s*default:\s*([^\n#]+)", text, re.M)
    if m and "/" in m.group(1):
        return m.group(1).split("/")[0].strip()
    return ""


def _hermes_python() -> str:
    for cand in ("/opt/homebrew/bin/hermes", "/usr/local/bin/hermes",
                 str(Path.home() / ".local" / "bin" / "hermes"), "/usr/bin/hermes"):
        if Path(cand).exists():
            return cand
    found = shutil.which("hermes")
    if not found:
        raise ApiError(503, "hermes CLI not found")
    return found


def _provider_model_ids(provider: str) -> list[str] | None:
    """Ask Hermes' own Python. None means "could not ask", which the page shows
    as unknown rather than as an empty catalogue."""
    code = (
        "import json,sys\n"
        "try:\n"
        "    from hermes_cli.models import provider_model_ids\n"
        "    print(json.dumps(list(provider_model_ids(sys.argv[1]))))\n"
        "except Exception as e:\n"
        "    print(json.dumps({'error': str(e)}))\n"
    )
    try:
        p = subprocess.run([_hermes_python(), "python", "-c", code, provider],
                           capture_output=True, text=True, timeout=45)
        data = json.loads((p.stdout or "").strip().splitlines()[-1])
        if isinstance(data, dict):
            return None
        return [str(x) for x in data]
    except Exception:
        return None


def models(req, query, body):               # noqa: ANN001
    import roster
    now = time.time()
    if _cache["value"] is not None and (now - _cache["at"]) < CACHE_TTL and \
            not str(query.get("force", "")).lower() in ("1", "true", "yes"):
        return _cache["value"]

    agents = roster.agents()["agents"]
    providers: dict[str, dict] = {}
    for a in agents:
        provider = _provider_of(a["profile"]) or "unknown"
        if provider not in providers:
            providers[provider] = {"provider": provider, "models": None}
    for provider, entry in providers.items():
        if provider == "unknown":
            entry["models"] = []
            continue
        entry["models"] = _provider_model_ids(provider) or []

    value = {
        "providers": list(providers.values()),
        "agents": [{"code": a["code"], "name": a["name"], "model": a["model"],
                    "provider": _provider_of(a["profile"]) or "unknown"} for a in agents],
        "fetched_at": now,
    }
    _cache.update({"at": now, "value": value})
    return value


def assign(req, query, body):               # noqa: ANN001
    if body is None:
        body = {}
    code = str(body.get("agent") or "").upper()
    model = str(body.get("model") or "").strip()
    if not code or not model:
        raise ApiError(400, "agent and model are required")
    import roster
    profile = roster.profile_of_code(code)
    if not profile:
        raise ApiError(404, f"no agent with code {code}")

    provider = _provider_of(profile)
    if provider and provider != "unknown":
        offered = _provider_model_ids(provider)
        if offered and model not in offered and f"{provider}/{model}" not in offered:
            raise ApiError(400, f"{provider} does not offer a model called {model}")

    path = _profile_home(profile) / "config.yaml"
    if not path.exists():
        path.write_text(f"model:\n  default: {model}\n", encoding="utf-8")
    else:
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^model:\s*\n(?:[ \t]+.*\n)*?[ \t]+default:", text, re.M):
            text = re.sub(r"(^model:\s*\n(?:[ \t]+.*\n)*?[ \t]+default:\s*)([^\n#]+)",
                          lambda m: m.group(1) + model, text, count=1, flags=re.M)
        else:
            text = f"model:\n  default: {model}\n" + text
        from files import BACKUP_DIR
        backup = BACKUP_DIR / profile / f"config.yaml.{time.strftime('%Y%m%d-%H%M%S')}"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        path.write_text(text, encoding="utf-8")

    store.audit("operator", "models.assign", {"profile": profile, "model": model})
    import roster as roster_mod
    roster_mod.invalidate()
    _cache["at"] = 0
    return {"agent": code, "model": model, "profile": profile}


def register(route, ApiError_):        # noqa: ANN001
    """Declare this module's routes. Called once by server.py at load time."""
    route("GET", "/api/models")(models)
    route("POST", "/api/models/assign")(assign)
