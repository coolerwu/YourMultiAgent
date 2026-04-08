from server.domain.agent.agent_entity import ChatMessageEntity, ChatSessionEntity, MemoryItemEntity
from server.domain.agent.session_history import build_runtime_messages


def test_build_runtime_messages_excludes_error_and_event_entries():
    session = ChatSessionEntity(
        id="session-1",
        title="test",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        summary="这是压缩摘要",
        memory_items=[
            MemoryItemEntity(
                id="m1",
                category="goal",
                content="保持简单对话模式",
                confidence=0.9,
                updated_at="2026-01-01T00:00:00+00:00",
            )
        ],
        messages=[
            ChatMessageEntity(
                id="u1",
                role="user",
                kind="user",
                content="你好",
                created_at="2026-01-01T00:00:00+00:00",
            ),
            ChatMessageEntity(
                id="e1",
                role="event",
                kind="tool_start",
                content="调用工具",
                created_at="2026-01-01T00:00:01+00:00",
            ),
            ChatMessageEntity(
                id="r1",
                role="error",
                kind="error",
                content="执行超时",
                created_at="2026-01-01T00:00:02+00:00",
            ),
            ChatMessageEntity(
                id="a1",
                role="assistant",
                kind="assistant",
                content="你好，请问需要什么帮助？",
                created_at="2026-01-01T00:00:03+00:00",
            ),
        ],
    )

    runtime_messages = build_runtime_messages(session)
    payloads = [msg.content for msg in runtime_messages]

    assert any("压缩摘要" in item for item in payloads)
    assert any("长期记忆" in item for item in payloads)
    assert any("[user] user: 你好" == item for item in payloads)
    assert any("[assistant] assistant: 你好，请问需要什么帮助？" == item for item in payloads)
    assert all("调用工具" not in item for item in payloads)
    assert all("执行超时" not in item for item in payloads)


def test_build_runtime_messages_can_skip_latest_user_message():
    session = ChatSessionEntity(
        id="session-2",
        title="test",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        messages=[
            ChatMessageEntity(
                id="u1",
                role="user",
                kind="user",
                content="旧消息",
                created_at="2026-01-01T00:00:00+00:00",
            ),
            ChatMessageEntity(
                id="a1",
                role="assistant",
                kind="assistant",
                content="收到",
                created_at="2026-01-01T00:00:01+00:00",
            ),
            ChatMessageEntity(
                id="u2",
                role="user",
                kind="user",
                content="最新问题",
                created_at="2026-01-01T00:00:02+00:00",
            ),
        ],
    )

    runtime_messages = build_runtime_messages(session, exclude_latest_user_message="最新问题")
    payloads = [msg.content for msg in runtime_messages]

    assert all("[user] user: 最新问题" not in item for item in payloads)
    assert any("[user] user: 旧消息" == item for item in payloads)
    assert any("[assistant] assistant: 收到" == item for item in payloads)
