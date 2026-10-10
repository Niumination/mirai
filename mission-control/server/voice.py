"""voice.py — a voice on this machine, and the modes that decide which one speaks.

Three modes, stored in ~/mirai/data/voice.json. THE MODE IS A NUMBER, because
the page compares it numerically and a string silently disables every control:
  1 local     you speak in the browser, the crew answers with the local voice service
  2 studio    you speak in the browser, the crew answers with ElevenLabs
  3 both      ElevenLabs both transcribes you and answers

2 and 3 FALL BACK to the local voice whenever ElevenLabs fails for any reason,
and the response says which engine actually spoke in an X-Voice-Engine header.

Be straight about transcription: this build makes speech OUT, not speech IN. Mode
1 has the browser listen and never calls /api/transcribe; modes 2 and 3 need
ElevenLabs. With neither, the route returns a clear error rather than an empty
string, which reads as a broken microphone.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import time
from pathlib import Path

import store
from server import ApiError, Raw

MIRAI_DIR = Path(os.environ.get("MIRAI_DIR", str(Path.home() / "mirai"))).expanduser()
DATA_DIR = Path(os.environ.get("MIRAI_DATA_DIR", str(MIRAI_DIR / "data"))).expanduser()
VOICE_JSON = DATA_DIR / "voice.json"
SECRETS_ENV = DATA_DIR / "secrets.env"

LOCAL_URL = os.environ.get("MIRAI_VOICE_URL", "http://127.0.0.1:8768")
START_COMMAND = "cd ~/mirai-voice && python3 voice-server.py 8768"
TRANSCRIBE_MAX = 12 * 1024 * 1024

MODE_INFO = {
    "1": {"name": "Local", "tags": ["offline", "private"],
          "note": "You speak in the browser; the crew answers with the local Piper voice."},
    "2": {"name": "Studio", "tags": ["ElevenLabs"],
          "note": "You speak in the browser; the crew answers with ElevenLabs. Falls back to local."},
    "3": {"name": "Both", "tags": ["ElevenLabs", "full duplex"],
          "note": "ElevenLabs both transcribes you and answers. Falls back to local for output."},
}
DEFAULT = {"mode": 1, "speed": 1.0, "auto_greet": True, "cast": {}, "engine": "piper"}


def _load() -> dict:
    try:
        data = json.loads(VOICE_JSON.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {**DEFAULT, **data}
    except Exception:
        pass
    return dict(DEFAULT)


def _save(cfg: dict) -> None:
    VOICE_JSON.parent.mkdir(parents=True, exist_ok=True)
    VOICE_JSON.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _get_json(url: str, timeout: float = 2.5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def _post_json(url: str, payload: dict, headers: dict | None = None, timeout: float = 30):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), dict(r.headers)


def _local_health() -> dict:
    h = _get_json(f"{LOCAL_URL}/health")
    return {"up": h is not None, **(h or {})}


def _local_voices() -> list[str]:
    v = _get_json(f"{LOCAL_URL}/voices")
    if isinstance(v, dict):
        return v.get("voices") or []
    return v if isinstance(v, list) else []


def _el_key() -> str | None:
    env = os.environ.get("ELEVENLABS_API_KEY")
    if env:
        return env.strip()
    try:
        for line in SECRETS_ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("ELEVENLABS_API_KEY="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def _save_el_key(key: str) -> None:
    lines = []
    if SECRETS_ENV.exists():
        lines = [l for l in SECRETS_ENV.read_text(encoding="utf-8").splitlines()
                 if not l.startswith("ELEVENLABS_API_KEY=")]
    lines.append(f"ELEVENLABS_API_KEY={key}")
    SECRETS_ENV.parent.mkdir(parents=True, exist_ok=True)
    SECRETS_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(SECRETS_ENV, 0o600)          # never into the database, never logged


def _elevenlabs_say(text: str, agent: str, cfg: dict, api_key: str) -> bytes:
    voice = (cfg.get("cast") or {}).get(agent) or "Rachel"
    payload = {"text": text, "model_id": "eleven_multilingual_v2",
               "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
    data, _ = _post_json(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                         payload, {"xi-api-key": api_key})
    return data


def _transcribe_elevenlabs(blob: bytes, api_key: str) -> str:
    boundary = "----mirai" + str(int(time.time()))
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"audio.webm\"\r\nContent-Type: audio/webm\r\n\r\n").encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    body = head + blob + tail
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/speech-to-text", data=body,
        headers={"xi-api-key": api_key, "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8", errors="replace"))
    return str(data.get("text") or "")


def _config_payload() -> dict:
    cfg = _load()
    health = _local_health()
    return {
        "mode": int(cfg.get("mode", 1)),
        "modes": MODE_INFO,
        "speed": cfg.get("speed", 1.0),
        "auto_greet": bool(cfg.get("auto_greet", True)),
        "cast": cfg.get("cast") or {},
        "el_key_present": bool(_el_key()),
        "engine": cfg.get("engine", "piper"),
        "engine_installed": Path(os.environ.get("MIRAI_VOICE_DIR", str(Path.home() / "mirai-voice"))).exists(),
        "engine_up": bool(health.get("up")),
        "engine_loading": bool(health.get("loading", False)),
        "engine_error": health.get("error"),
        "engine_voices": _local_voices() or health.get("voices") or [],
        "engine_memory_mb": health.get("memory_mb"),
        "start_command": START_COMMAND,
        "piper_voices": _local_voices(),
        "agent_engines": {a["code"]: _agent_engine(a["code"]) for a in _agents()},
    }


def _agents():
    import roster
    return roster.agents().get("agents", [])


def _agent_engine(code: str) -> str:
    return "local" if (not _el_key()) else "elevenlabs"


def config(req, query, body):               # noqa: ANN001
    return {"config": _config_payload()}


def config_post(req, query, body):          # noqa: ANN001
    if body is None:
        body = {}
    cfg = _load()
    if "mode" in body:
        try:
            m = int(body["mode"])
        except (TypeError, ValueError):
            raise ApiError(400, "mode must be the number 1, 2 or 3")
        if m not in (1, 2, 3):
            raise ApiError(400, "mode must be the number 1, 2 or 3")
        cfg["mode"] = m
    if "speed" in body:
        try:
            speed = float(body["speed"])
        except (TypeError, ValueError):
            raise ApiError(400, "speed must be a number")
        cfg["speed"] = max(0.5, min(2.0, speed))
    if "auto_greet" in body:
        cfg["auto_greet"] = bool(body["auto_greet"])
    if "cast" in body:
        if not isinstance(body["cast"], dict):
            raise ApiError(400, "cast must be an object of agent code -> voice name")
        cfg["cast"] = {str(k).upper(): str(v) for k, v in body["cast"].items()}
    _save(cfg)
    store.audit("operator", "voice.config", {k: cfg[k] for k in ("mode", "speed", "auto_greet", "cast")})
    return {"config": _config_payload()}    # the whole object: the page assigns it straight on


def engine(req, query, body):               # noqa: ANN001
    if body is None:
        body = {}
    name = str(body.get("engine") or "").strip().lower()
    if name not in ("piper", "say"):
        # 'say' is the macOS built-in, offered as a light alternative to Piper.
        raise ApiError(400, "engine must be piper or say")
    cfg = _load()
    cfg["engine"] = name
    _save(cfg)
    return {"config": _config_payload()}


def elevenlabs_key(req, query, body):       # noqa: ANN001
    if body is None:
        body = {}
    key = str(body.get("key") or "").strip()
    if not key:
        raise ApiError(400, "key is required")
    try:
        req2 = urllib.request.Request("https://api.elevenlabs.io/v1/voices",
                                      headers={"xi-api-key": key})
        with urllib.request.urlopen(req2, timeout=20) as r:
            if r.status != 200:
                raise ApiError(400, "ElevenLabs rejected that key")
    except urllib.error.HTTPError as e:
        raise ApiError(400, f"ElevenLabs rejected that key ({e.code})")
    except Exception as e:
        raise ApiError(502, f"could not reach ElevenLabs to validate the key: {e}")
    _save_el_key(key)
    store.audit("operator", "voice.key", {"validated": True})   # the key itself is never recorded
    return {"config": _config_payload()}


def voices(req, query, body):               # noqa: ANN001
    cfg = _load()
    local = _local_voices()
    out = []
    for a in _agents():
        name = (cfg.get("cast") or {}).get(a["code"])
        out.append({"code": a["code"], "kokoro": name or (local[0] if local else ""),
                    "engine": _agent_engine(a["code"]), "options": local})
    return {"agents": out, "piper_voices": local}


def health(req, query, body):               # noqa: ANN001
    h = _local_health()
    return {"local": h, "url": LOCAL_URL, "start_command": START_COMMAND}


def say(req, query, body):                  # noqa: ANN001
    if body is None:
        body = {}
    text = str(body.get("text") or "").strip()
    agent = str(body.get("agent") or "").strip().upper()
    if not text:
        raise ApiError(400, "text is required")
    cfg = _load()
    mode = int(cfg.get("mode", 1))
    engine_used = "local"

    if mode in (2, 3) and _el_key():
        try:
            audio = _elevenlabs_say(text, agent, cfg, _el_key())
            engine_used = "elevenlabs"
            return Raw(audio, "audio/mpeg", {"X-Voice-Engine": engine_used})
        except Exception:
            engine_used = "local"          # 2 and 3 FALL BACK, for any reason

    audio, ctype = _local_say(text, agent, cfg)
    return Raw(audio, ctype, {"X-Voice-Engine": engine_used})


def _local_say(text: str, agent: str, cfg: dict) -> tuple[bytes, str]:
    voice = (cfg.get("cast") or {}).get(agent)
    try:
        payload = {"text": text, "voice": voice, "speed": cfg.get("speed", 1.0),
                   "engine": cfg.get("engine", "piper")}
        data, headers = _post_json(f"{LOCAL_URL}/say", payload)
        return data, headers.get("Content-Type", "audio/wav")
    except Exception as e:
        raise ApiError(503, f"the local voice service is not answering at {LOCAL_URL} "
                            f"({e}). Start it with: {START_COMMAND}")


# /api/transcribe is posted a recorded blob, not JSON, so it goes in RAW_BODY_PATHS.
RAW_BODY_PATHS = {"/api/transcribe"}


def transcribe(req, query, body):           # noqa: ANN001
    blob = body if isinstance(body, (bytes, bytearray)) else b""
    if not blob:
        raise ApiError(400, "no audio arrived")
    if len(blob) > TRANSCRIBE_MAX:
        raise ApiError(413, "audio is over the 12 MB limit")
    key = _el_key()
    cfg = _load()
    if int(cfg.get("mode", 1)) == 1 or not key:
        raise ApiError(501, "this build does not transcribe locally: mode 1 has the browser "
                            "listen instead, and modes 2 and 3 need an ElevenLabs key")
    try:
        text = _transcribe_elevenlabs(bytes(blob), key)
    except Exception as e:
        raise ApiError(502, f"transcription failed: {e}")
    return {"text": text}


def greeting_text(req, query, body):        # noqa: ANN001
    code = (query.get("agent") or "").upper()
    if not code:
        # The console asks for the greeting without naming an agent: the one the
        # owner talks to is the first on the roster, not an error.
        code = (_agents() or [{}])[0].get("code", "")
    cfg = _load()
    owner = store.settings().get("display_name") or store.settings().get("operator_name") or "there"
    agent = next((a for a in _agents() if a["code"] == code), None)
    if not agent:
        raise ApiError(404, f"no agent with code {code}")
    role = agent["role"]
    # "<its role sentence, in the second person>"
    second = role.replace("You are ", "").replace("You ", "I ").strip()
    text = f"Hello {owner}. {agent['name']} here. {second}"
    return {"text": text, "auto_greet": bool(cfg.get("auto_greet", True)), "agent": code}


def greeting(req, query, body):             # noqa: ANN001
    payload = greeting_text(req, query, body)
    if not payload["auto_greet"]:
        raise ApiError(409, "auto_greet is off")
    cfg = _load()
    agent = payload["agent"]
    mode = int(cfg.get("mode", 1))
    engine_used = "local"
    if mode in (2, 3) and _el_key():
        try:
            audio = _elevenlabs_say(payload["text"], agent, cfg, _el_key())
            return Raw(audio, "audio/mpeg", {"X-Voice-Engine": "elevenlabs"})
        except Exception:
            engine_used = "local"
    audio, ctype = _local_say(payload["text"], agent, cfg)
    return Raw(audio, ctype, {"X-Voice-Engine": engine_used})


def register(route, ApiError_):             # noqa: ANN001
    """Declare this module's routes. Called once by server.py at load time."""
    route("GET", "/api/voice/config")(config)
    route("POST", "/api/voice/config")(config_post)
    route("POST", "/api/voice/engine")(engine)
    route("POST", "/api/voice/elevenlabs-key")(elevenlabs_key)
    route("GET", "/api/voice/voices")(voices)
    route("GET", "/api/voice/health")(health)
    route("POST", "/api/voice")(say)
    route("POST", "/api/transcribe")(transcribe)
    route("GET", "/api/greeting")(greeting)
    route("GET", "/api/greeting/text")(greeting_text)
