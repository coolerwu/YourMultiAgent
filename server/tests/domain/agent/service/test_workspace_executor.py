"""
tests/domain/agent/service/test_workspace_executor.py

WorkspaceExecutor 单测：覆盖 Worker 顺序与执行者事件。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from server.domain.agent.entity.agent_entity import AgentEntity, ChatMessageEntity, ChatSessionEntity, LLMProvider, WorkspaceEntity
from server.domain.agent.service.workspace_executor import WorkspaceExecutor


class FakeLLM:
    def bind_tools(self, _tools):
        return self

    async def astream(self, messages):
        last = messages[-1].content
        if "可用 Worker" in last:
            yield SimpleNamespace(content="先产品后研发", tool_calls=[])
            return
        role = last.split("你当前负责的角色：", 1)[-1].splitlines()[0].strip()
        yield SimpleNamespace(content=f"{role} 已完成", tool_calls=[])


@pytest.mark.asyncio
async def test_workspace_executor_runs_workers_by_order_and_emits_actor_name(tmp_path):
    workspace = WorkspaceEntity(
        id="ws-1",
        name="Demo",
        work_dir=str(tmp_path),
        coordinator=AgentEntity(
            id="coordinator",
            name="主控智能体",
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
            system_prompt="你是主控",
            order=0,
        ),
        workers=[
            AgentEntity(
                id="dev",
                name="研发",
                provider=LLMProvider.ANTHROPIC,
                model="claude-sonnet-4-6",
                system_prompt="你是研发",
                order=2,
            ),
            AgentEntity(
                id="product",
                name="产品",
                provider=LLMProvider.ANTHROPIC,
                model="claude-sonnet-4-6",
                system_prompt="你是产品",
                order=1,
            ),
        ],
    )
    worker_gateway = MagicMock()
    worker_gateway.list_capabilities.return_value = []
    worker_gateway.invoke = AsyncMock()
    llm_factory = MagicMock()
    llm_factory.build.return_value = FakeLLM()

    executor = WorkspaceExecutor(workspace, worker_gateway, llm_factory)
    session = ChatSessionEntity(
        id="session-1",
        title="测试会话",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        messages=[
            ChatMessageEntity(
                id="msg-1",
                role="user",
                kind="user",
                content="先做产品方案",
                created_at="2026-01-01T00:00:00+00:00",
            )
        ],
    )
    events = [event async for event in executor.run("做一个页面", session)]

    starts = [event for event in events if event["type"] == "worker_start"]
    assert [event["node_name"] for event in starts] == ["产品", "研发"]

    summaries = [event for event in events if event["type"] == "worker_result"]
    assert summaries[0]["actor_name"] == "产品"
    assert summaries[1]["actor_name"] == "研发"

    shared_dir = tmp_path / "shared"
    assert shared_dir.exists()
