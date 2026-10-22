"""house.py — Niumination window: ten seats, wiki, five cron, gateway as a lamp.

Read only. Does not start, stop, or reconfigure Hermes.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import avatars as avatars_mod
import roster

HOME = Path.home()
HERMES = Path(os.environ.get("HERMES_HOME", str(HOME / ".hermes"))).expanduser()

# Function per Telegram thread id — locked with the owner 2026-10-10.
SEATS = (
    {
        "thread_id": "1", "code": "TR", "name": "General",
        "job": "Inbox manusia: sapaan, arahkan ke topik yang benar. Tidak mendelegasi, tidak nulis kode.",
        "not_this": "Bukan bos kru.",
    },
    {
        "thread_id": "802", "code": "RS", "name": "Research",
        "job": "Cari, kutip, provenance, file wiki research.",
        "not_this": "Bukan Builder.",
    },
    {
        "thread_id": "803", "code": "BD", "name": "Builder",
        "job": "Ubah kode / repo. Satu PR, satu diff.",
        "not_this": "Bukan yang meng-QA hasil sendiri sebagai putusan akhir.",
    },
    {
        "thread_id": "804", "code": "QA", "name": "QA",
        "job": "Review, tes, audit. Putusan lolos atau tidak.",
        "not_this": "Bukan yang menulis fitur.",
    },
    {
        "thread_id": "1172", "code": "KR", "name": "Kreator",
        "job": "Brand, copy, humanizer, video kampanye.",
        "not_this": "Bukan kurikulum / slide dinas.",
    },
    {
        "thread_id": "7402", "code": "SB", "name": "Serbaguna",
        "job": "Sandbox / eksperimen. Hasil berguna dipindah ke spesialis lalu di-file wiki.",
        "not_this": "Bukan bak sampah karena malas pilih topik.",
    },
    {
        "thread_id": "8853", "code": "AS", "name": "ASN",
        "job": "SKP, rapat, weekly dinas Aceh Tengah. Provider huancheng.",
        "not_this": "Bukan Serbaguna, bukan kode, bukan edu umum.",
    },
    {
        "thread_id": "12595", "code": "CR", "name": "Cron & Otomasi",
        "job": "Hanya laporan otomatis / gagal job / heartbeat.",
        "not_this": "Bukan tempat manusia minta bikin skrip.",
    },
    {
        "thread_id": "12707", "code": "ED", "name": "Edu Content",
        "job": "Kurikulum, doc-pipeline, materi ajar.",
        "not_this": "Bukan konten brand.",
    },
    {
        "thread_id": "13902", "code": "OR", "name": "Orkestrator",
        "job": "Satu-satunya bos: pecah kerja, kanban, subagent, pilih topik tujuan.",
        "not_this": "Bukan chat basa-basi.",
    },
)

CRON_WANTED = (
    ("wiki-opening-snapshot", "02:20"),
    ("wiki-dropbox", "every 30 min"),
    ("wiki-librarian", "02:30"),
    ("wiki-lint", "02:50"),
    ("wiki-closing-snapshot", "03:10"),
)
CRON_FORBIDDEN = ("wiki-mail-sweep", "wiki-offsite")

TOPICS_MAP = Path(__file__).resolve().parents[2] / "fleet" / "plugins" / "telegram_topic_profiles" / "topics.json"


def _job_names() -> set[str]:
    names: set[str] = set()
    paths = [HERMES / "cron" / "jobs.json"]
    pdir = HERMES / "profiles"
    if pdir.is_dir():
        for child in pdir.iterdir():
            paths.append(child / "cron" / "jobs.json")
    paths.append(HERMES / "profiles" / "default" / "cron" / "jobs.json")
    for p in paths:
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            continue
        jobs = data.get("jobs") if isinstance(data, dict) else data
        if not isinstance(jobs, list):
            continue
        for j in jobs:
            if isinstance(j, dict) and j.get("name"):
                names.add(str(j["name"]))
            elif isinstance(j, str):
                names.add(j)
    return names


def snapshot() -> dict:
    wiki = roster._wiki_dir()
    wiki_exists = wiki.is_dir()
    age = roster._wiki_heartbeat_age()
    wiki_alive = bool(wiki_exists and age is not None and age < 40 * 60)
    gw = roster.gateway()
    ticker = roster.cron_ticker()
    present = _job_names()
    cron_jobs = []
    for name, when in CRON_WANTED:
        cron_jobs.append({
            "name": name,
            "when": when,
            "present": name in present,
            "wanted": True,
        })
    forbidden_live = [n for n in CRON_FORBIDDEN if n in present]
    prompts = roster._yaml_scalar_map(roster._hermes_config_text(), "channel_prompts")
    seats = []
    for s in SEATS:
        row = dict(s)
        row["in_yaml"] = s["thread_id"] in prompts or (
            s["thread_id"] == "1" and bool(prompts)
        )
        # thread 1 is often the main agent (no map); treat yaml file existing as bound.
        if s["thread_id"] == "1":
            row["in_yaml"] = bool(roster._hermes_config_text())
        row["avatar"] = avatars_mod.pack_for(s["code"])
        seats.append(row)

    chat_title, plugin = "Niu-MissionControl", "off"
    if TOPICS_MAP.is_file():
        try:
            m = json.loads(TOPICS_MAP.read_text(encoding="utf-8"))
            chat_title = m.get("chat_title") or chat_title
            plugin = m.get("plugin") or plugin
        except (OSError, json.JSONDecodeError):
            pass

    return {
        "product": "niumination-window",
        "wiki": {
            "path": str(wiki),
            "exists": wiki_exists,
            "heartbeat_s": None if age is None else round(age, 1),
            "alive": wiki_alive,
        },
        "gateway": {
            "up": bool(gw.get("up")),
            "note": "Hermes' own process. This window does not restart it.",
        },
        "cron": {
            "ticker": ticker,
            "jobs": cron_jobs,
            "wanted": 5,
            "present": sum(1 for j in cron_jobs if j["present"]),
            "forbidden_live": forbidden_live,
        },
        "telegram": {
            "title": chat_title,
            "plugin": plugin,
            "router": "config.yaml",
        },
        "profile": "default",
        "seats": seats,
        "now": time.time(),
    }


def house(_req, _query, _body):
    return snapshot()


def register(route, ApiError_):  # noqa: ANN001
    route("GET", "/api/house")(house)
