"""
domain/agent/session_history.py

会话历史、自动 compact 与 memory 提取的工具。
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from langchain_core.messages import HumanMessage

from server.domain.agent.agent_entity import ChatMessageEntity, ChatSessionEntity, MemoryItemEntity

RECENT_MESSAGE_WINDOW = 12
COMPACT_MESSAGE_THRESHOLD = 24
MAX_SUMMARY_SNIPPETS = 10
MAX_MEMORY_ITEMS = 12


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def create_session(title_hint: str = "") -> ChatSessionEntity:
    timestamp = now_iso()
    return ChatSessionEntity(
        id=str(uuid.uuid4()),
        title=build_session_title(title_hint),
        created_at=timestamp,
        updated_at=timestamp,
    )


def build_session_title(text: str) -> str:
    stripped = " ".join(text.strip().split())
    if not stripped:
        return "新会话"
    return stripped[:32]


def append_session_message(
    session: ChatSessionEntity,
    *,
    role: str,
    kind: str,
    content: str,
    actor_id: str = "",
    actor_name: str = "",
    node: str = "",
    session_round: int = 0,
) -> ChatMessageEntity:
    message = ChatMessageEntity(
        id=str(uuid.uuid4()),
        role=role,
        kind=kind,
        content=content,
        created_at=now_iso(),
        actor_id=actor_id,
        actor_name=actor_name,
        node=node,
        session_round=session_round,
    )
    session.messages.append(message)
    session.message_count = len(session.messages)
    session.updated_at = message.created_at
    return message


def needs_compact(session: ChatSessionEntity) -> bool:
    return len(session.messages) > COMPACT_MESSAGE_THRESHOLD


def build_compact_source(session: ChatSessionEntity) -> str:
    earlier = session.messages[:-RECENT_MESSAGE_WINDOW]
    lines: list[str] = []
    if session.summary.strip():
        lines.append("【已有摘要】")
        lines.append(session.summary.strip())
        lines.append("")
    lines.append("【待压缩历史消息】")
    for item in earlier:
        text = " ".join(item.content.split())
        if not text:
            continue
        actor = item.actor_name or item.role
        lines.append(f"[{item.kind}] {actor}: {text[:600]}")
    return "\n".join(lines).strip()


def refresh_session_summary(session: ChatSessionEntity) -> str:
    if len(session.messages) <= COMPACT_MESSAGE_THRESHOLD:
        return session.summary

    earlier = session.messages[:-RECENT_MESSAGE_WINDOW]
    snippets: list[str] = []
    for item in earlier[-MAX_SUMMARY_SNIPPETS:]:
        text = " ".join(item.content.split())
        if not text:
            continue
        actor = item.actor_name or item.role
        snippets.append(f"{actor}: {text[:120]}")
    if not snippets:
        return session.summary

    previous = session.summary.strip()
    merged = snippets if not previous else [previous, *snippets]
    session.summary = "\n".join(merged[-MAX_SUMMARY_SNIPPETS:])
    session.updated_at = now_iso()
    return session.summary


def refresh_session_memory(session: ChatSessionEntity) -> list[MemoryItemEntity]:
    source_messages = session.messages[-RECENT_MESSAGE_WINDOW:]
    memory_by_key: dict[tuple[str, str], MemoryItemEntity] = {
        (item.category, item.content): item for item in session.memory_items
    }

    for message in source_messages:
        for item in _extract_memory_candidates(message):
            key = (item.category, item.content)
            existing = memory_by_key.get(key)
            if existing is None:
                memory_by_key[key] = item
            else:
                existing.updated_at = item.updated_at
                existing.source_message_ids = sorted(set(existing.source_message_ids + item.source_message_ids))
                existing.confidence = max(existing.confidence, item.confidence)

    memory_items = list(memory_by_key.values())
    memory_items.sort(key=lambda item: item.updated_at, reverse=True)
    session.memory_items = memory_items[:MAX_MEMORY_ITEMS]
    return session.memory_items


def build_runtime_messages(
    session: ChatSessionEntity,
    *,
    exclude_latest_user_message: str = "",
) -> list:
    runtime_messages: list = []
    if session.summary.strip():
        runtime_messages.append(
            HumanMessage(
                content="以下是此前会话的压缩摘要，请延续上下文并避免重复提问：\n" + session.summary.strip()
            )
        )
    if session.memory_items:
        memory_lines = [f"- [{item.category}] {item.content}" for item in session.memory_items]
        runtime_messages.append(
            HumanMessage(
                content="以下是会话中已确认的长期记忆，请优先遵守：\n" + "\n".join(memory_lines)
            )
        )

    recent_messages = session.messages[-RECENT_MESSAGE_WINDOW:]
    skipped_latest_user_id = ""
    candidate = exclude_latest_user_message.strip()
    if candidate:
        for item in reversed(recent_messages):
            if item.role != "user":
                continue
            if item.content.strip() != candidate:
                continue
            skipped_latest_user_id = item.id
            break

    for item in recent_messages:
        if item.role not in {"user", "assistant"}:
            continue
        if skipped_latest_user_id and item.id == skipped_latest_user_id:
            skipped_latest_user_id = ""
            continue
        content = item.content.strip()
        if not content:
            continue
        actor = item.actor_name or item.role
        runtime_messages.append(HumanMessage(content=f"[{item.kind}] {actor}: {content}"))
    return runtime_messages


def summarize_memory(memory_items: list[MemoryItemEntity]) -> list[dict]:
    return [
        {
            "id": item.id,
            "category": item.category,
            "content": item.content,
            "confidence": item.confidence,
            "updated_at": item.updated_at,
        }
        for item in memory_items
    ]


def _extract_memory_candidates(message: ChatMessageEntity) -> list[MemoryItemEntity]:
    text = " ".join(message.content.split())
    if not text:
        return []

    categories: list[tuple[str, str, float]] = []
    if message.role == "user":
        categories.append(("goal", text[:200], 0.95))
    if message.kind == "summary":
        categories.append(("decision", text[:220], 0.85))

    for path in re.findall(r"(?:`([^`]+)`|([A-Za-z0-9_./-]+\.[A-Za-z0-9]+))", message.content):
        candidate = next((item for item in path if item), "").strip()
        if candidate:
            categories.append(("artifact", candidate, 0.9))

    lowered = text.lower()
    if any(token in lowered for token in ["不要", "必须", "仅", "限制", "约束", "禁止"]):
        categories.append(("constraint", text[:200], 0.8))

    items: list[MemoryItemEntity] = []
    for category, content, confidence in categories:
        items.append(
            MemoryItemEntity(
                id=str(uuid.uuid4()),
                category=category,
                content=content,
                confidence=confidence,
                source_message_ids=[message.id],
                updated_at=now_iso(),
            )
        )
    return items
