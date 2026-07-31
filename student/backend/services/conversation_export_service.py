"""把当前用户对话导出为可用于清洗/微调的 JSONL。"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, Iterator

from database import get_db


SECRET_PATTERNS = (
    re.compile(r"\btvly-[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{10,}\b", re.IGNORECASE),
    re.compile(r"\bpostgres(?:ql)?://[^\s\"']+\b", re.IGNORECASE),
)
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")


def _redact_text(value: str, anonymize: bool) -> str:
    text = str(value or "")
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED_SECRET]", text)
    if anonymize:
        text = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
        text = PHONE_PATTERN.sub("[REDACTED_PHONE]", text)
    return text


def _safe_value(value: Any, anonymize: bool) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _safe_value(item, anonymize)
            for key, item in value.items()
            if str(key).lower() not in {"api_key", "search_api_key", "embedding_api_key", "image_api_key"}
        }
    if isinstance(value, list):
        return [_safe_value(item, anonymize) for item in value]
    if isinstance(value, str):
        return _redact_text(value, anonymize)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _parse_json(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def iter_conversation_jsonl(user_id: int, *, anonymize: bool = True) -> Iterator[str]:
    conn = get_db()
    try:
        sessions = conn.execute(
            """SELECT id, title, summary, turn_count, created_at, last_active_at
               FROM conversation_sessions
               WHERE user_id = ?
               ORDER BY id ASC""",
            (user_id,),
        ).fetchall()
        for session in sessions:
            rows = conn.execute(
                """SELECT role, content, knowledge_tags, metadata, created_at
                   FROM conversation_messages
                   WHERE user_id = ? AND session_id = ?
                   ORDER BY id ASC""",
                (user_id, session["id"]),
            ).fetchall()
            messages = []
            tool_trace = []
            knowledge_tags: set[str] = set()
            for row in rows:
                role = str(row["role"] or "")
                if role not in {"user", "assistant", "system"}:
                    continue
                content = _redact_text(row["content"], anonymize)
                if not content:
                    continue
                messages.append({"role": role, "content": content})
                tags = _parse_json(row["knowledge_tags"], [])
                knowledge_tags.update(str(tag) for tag in tags if tag)
                metadata = _parse_json(row["metadata"], {})
                if metadata.get("tool_events"):
                    tool_trace.extend(metadata["tool_events"])

            # 至少一问一答才是可训练样本。
            roles = {message["role"] for message in messages}
            if not messages or not {"user", "assistant"}.issubset(roles):
                continue
            item = {
                "messages": messages,
                "metadata": {
                    "source": "ai_learning_platform",
                    "conversation_id": int(session["id"]),
                    "title": _redact_text(session["title"], anonymize),
                    "knowledge_tags": sorted(knowledge_tags),
                    "turn_count": int(session["turn_count"] or 0),
                    "created_at": _safe_value(session["created_at"], anonymize),
                    "last_active_at": _safe_value(session["last_active_at"], anonymize),
                    "tool_trace": _safe_value(tool_trace, anonymize),
                    "anonymized": bool(anonymize),
                },
            }
            yield json.dumps(item, ensure_ascii=False, default=str) + "\n"
    finally:
        conn.close()
