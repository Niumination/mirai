"""settings.py — who is running this, and how the dashboard behaves.

Four keys, and the set is closed: display_name, operator_name, timezone and
voice_engine. Anything else is a 400, which is why avatar choices live in their
own table (avatars.py) instead of as settings.XX rows.

operator_name is READ ONLY here. It is what the crew calls the owner and it
lives in THEIR files (~/.hermes/memories/USER.md), not in ours. A POST that
includes it is refused with a 400 that says so.
"""
from __future__ import annotations

import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import store
from server import ApiError

WRITABLE = ("display_name", "timezone", "voice_engine")
READ_ONLY = ("operator_name",)
ALL_KEYS = WRITABLE + READ_ONLY
MAX_DISPLAY_NAME = 24


def _current() -> dict:
    s = store.settings()
    # What the crew calls the owner overrides the system-user default, so there
    # is one answer and not two. Expected to fall back on a fresh crew.
    hers = store.operator_name_from_hermes()
    if hers:
        s["operator_name"] = hers
    return {k: s.get(k) for k in ALL_KEYS}


def get_settings(req, query, body):         # noqa: ANN001
    return {"settings": _current()}


def post_settings(req, query, body):        # noqa: ANN001
    if body is None:
        body = {}
    if not isinstance(body, dict):
        raise ApiError(400, "body must be a JSON object")
    # The page sends {settings: {...}}; a bare object is accepted too.
    changes = body.get("settings") if isinstance(body.get("settings"), dict) else body

    unknown = [k for k in changes if k not in ALL_KEYS]
    if unknown:
        raise ApiError(400, f"unknown setting: {unknown[0]}")

    if "operator_name" in changes:
        raise ApiError(400, "operator_name is read only: it is what the crew calls you "
                            "and it lives in their own files, not in MIRAI's store")

    cleaned: dict = {}
    if "display_name" in changes:
        value = changes["display_name"]
        if not isinstance(value, str):
            raise ApiError(400, "display_name must be a string")
        value = value.strip()
        if len(value) > MAX_DISPLAY_NAME:
            raise ApiError(400, f"display_name is limited to {MAX_DISPLAY_NAME} characters "
                                f"(got {len(value)}) — the header is built for a first name")
        cleaned["display_name"] = value

    if "timezone" in changes:
        tz = changes["timezone"]
        if not isinstance(tz, str):
            raise ApiError(400, "timezone must be a string")
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError, KeyError):
            raise ApiError(400, f"unknown timezone: {tz}")
        cleaned["timezone"] = tz

    if "voice_engine" in changes:
        engine = changes["voice_engine"]
        if engine not in ("local", "studio", "both"):
            raise ApiError(400, "voice_engine must be one of: local, studio, both")
        cleaned["voice_engine"] = engine

    if not cleaned:
        # An empty object changes nothing and writes no audit row.
        return {"settings": _current()}

    store.save_settings(cleaned)
    store.audit("operator", "settings.save", {"keys": sorted(cleaned), "at": time.time()})
    return {"settings": _current()}


def register(route, ApiError_):        # noqa: ANN001
    """Declare this module's routes. Called once by server.py at load time."""
    route("GET", "/api/settings")(get_settings)
    route("POST", "/api/settings")(post_settings)
