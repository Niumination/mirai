"""Route Telegram forum topics to Hermes profiles (out of tree, update safe).

This file is exactly the plugin from the tutorial: a hook on
pre_gateway_dispatch that reads the incoming message's thread id and sets
source.profile before the gateway decides who answers.

Do NOT patch anything under ~/.hermes/hermes-agent/: it is overwritten on every
update. This plugin lives beside it, in ~/.hermes/plugins/.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
_MAP_PATH = Path(__file__).with_name("topics.json")


def _load_map():
    try:
        data = json.loads(_MAP_PATH.read_text())
        chat_id = str(data.get("chat_id", "")).strip()
        topics = {str(k): str(v) for k, v in (data.get("topics") or {}).items()}
        return chat_id, topics
    except FileNotFoundError:
        return "", {}
    except Exception as e:
        logger.warning("telegram_topic_profiles: bad topics.json: %s", e)
        return "", {}


def _route(**kwargs):
    event = kwargs.get("event")
    source = getattr(event, "source", None)
    if source is None:
        return None
    platform = getattr(source, "platform", None)
    pval = getattr(platform, "value", platform)
    if str(pval).lower() != "telegram":
        return None
    thread_id = getattr(source, "thread_id", None)
    if not thread_id or getattr(source, "profile", None):
        return None
    map_chat, topics = _load_map()
    chat_id = getattr(source, "chat_id", None)
    if map_chat and chat_id and str(chat_id) != map_chat:
        return None
    profile = topics.get(str(thread_id))
    if profile:
        source.profile = profile
        logger.info("telegram_topic_profiles: thread %s -> %s", thread_id, profile)
    return None


def register(ctx) -> None:
    ctx.register_hook("pre_gateway_dispatch", _route)
