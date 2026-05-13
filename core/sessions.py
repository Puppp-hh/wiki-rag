"""多用户会话存储：每个 session 一个 JSON 文件，保存在 data/sessions/。"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from core.utils import SESSIONS_DIR

SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def normalize_session_id(session_id: Optional[str]) -> str:
    if session_id and SESSION_RE.match(session_id):
        return session_id
    return uuid.uuid4().hex


def session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{normalize_session_id(session_id)}.json"


def load_session(session_id: str) -> dict:
    path = session_path(session_id)
    if not path.exists():
        return {"session_id": session_id, "messages": []}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {"session_id": session_id, "messages": []}
    data.setdefault("session_id", session_id)
    data.setdefault("messages", [])
    return data


def append_messages(session_id: str, messages: Iterable[dict]) -> None:
    session_id = normalize_session_id(session_id)
    data = load_session(session_id)
    existing = data.setdefault("messages", [])
    now = datetime.now().isoformat(timespec="seconds")
    for msg in messages:
        existing.append(
            {
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
                "createdAt": msg.get("createdAt", now),
                "hits": msg.get("hits"),
            }
        )
    data["updatedAt"] = now
    data["messages"] = existing[-500:]
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = session_path(session_id)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_session(session_id: str) -> None:
    path = session_path(session_id)
    if path.exists():
        path.unlink()
