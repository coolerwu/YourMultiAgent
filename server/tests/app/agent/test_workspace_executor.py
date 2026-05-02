"""
tests/app/agent/test_workspace_executor.py

WorkspaceExecutor 单测：覆盖 Worker 顺序与执行者事件。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from server.domain.agent.agent_entity import AgentEntity, ChatMessageEntity, ChatSessionEntity, LLMProvider, WorkspaceEntity, WorkspaceKind
from server.app.agent.workspace_executor import WorkspaceExecutor, _build_agent_system_prompt
from server.domain.worker.capability_entity import CapabilityEntity


class FakeLLM:
    def __init__(self):
        self.seen_messages = []

    def bind_tools(self, _tools):
        return self

    async def astream(self, messages):
        self.seen_messages.append(messages)
        last = messages[-1].content
        if "可用 Worker" in last:
            yield SimpleNamespace(content="先产品后研发", tool_calls=[])
            return
        role = last.split("你当前负责的角色：", 1)[-1].splitlines()[0].strip()
        yield SimpleNamespace(content=f"{role} 已完成", tool_calls=[])


class StructuredPlanLLM:
    def __init__(self):
        self.seen_messages = []

    def bind_tools(self, _tools):
        return self

    async def astream(self, messages):
        self.seen_messages.append(messages)
        last = messages[-1].content
        if "可用 Worker" in last:
            yield SimpleNamespace(
                content=(
                    '{"tasks":['
                    '{"id":"task-product","worker_id":"product","instruction":"输出产品方案","dependencies":[]},'
                    '{"id":"task-dev","worker_id":"dev","instruction":"基于产品方案实现","dependencies":["task-product"]}'
                    ']}'
                ),
                tool_calls=[],
            )
            return
        if "当前任务 ID：task-product" in last:
            yield SimpleNamespace(content="产品方案见 `shared/product.md`", tool_calls=[])
            return
        if "当前任务 ID：task-dev" in last:
            assert "task-product: 产品方案见 `shared/product.md`" in last
            yield SimpleNamespace(content="研发实现完成", tool_calls=[])
            return
        yield SimpleNamespace(content="完成", tool_calls=[])


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


def test_build_agent_system_prompt_includes_browser_guidance():
    agent = AgentEntity(
        id="browser-agent",
        name="浏览器执行",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        system_prompt="你是浏览器执行助手。",
    )
    prompt = _build_agent_system_prompt(
        agent,
        [
            CapabilityEntity(name="browser_open", description="打开页面", category="browser_read"),
            CapabilityEntity(name="browser_click", description="点击元素", category="browser_write", risk_level="medium"),
            CapabilityEntity(name="browser_get_text", description="读取文本", category="browser_read"),
        ],
    )

    assert "browser_open" in prompt
    assert "session_id" in prompt
    assert "先读取再交互" in prompt
    assert "高风险浏览器写工具" in prompt


@pytest.mark.asyncio
async def test_workspace_executor_injects_browser_guidance_into_system_prompt(tmp_path):
    workspace = WorkspaceEntity(
        id="ws-2",
        name="Browser Demo",
        work_dir=str(tmp_path),
        coordinator=AgentEntity(
            id="coordinator",
            name="主控智能体",
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
            system_prompt="你是主控",
            tools=["browser_open", "browser_click"],
        ),
        workers=[],
    )
    worker_gateway = MagicMock()
    worker_gateway.list_capabilities.return_value = [
        CapabilityEntity(name="browser_open", description="打开页面", category="browser_read"),
        CapabilityEntity(name="browser_click", description="点击元素", category="browser_write", risk_level="medium"),
    ]
    worker_gateway.invoke = AsyncMock()
    llm = FakeLLM()
    llm_factory = MagicMock()
    llm_factory.build.return_value = llm

    executor = WorkspaceExecutor(workspace, worker_gateway, llm_factory)
    session = ChatSessionEntity(
        id="session-2",
        title="测试会话",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    _ = [event async for event in executor.run("打开网页检查内容", session)]

    system_messages = [batch[0].content for batch in llm.seen_messages if batch]
    assert any("工具使用约束" in item for item in system_messages)
    assert any("browser_close" in item for item in system_messages)


@pytest.mark.asyncio
async def test_workspace_executor_runs_structured_task_dag_and_records_artifacts(tmp_path):
    workspace = WorkspaceEntity(
        id="ws-dag",
        name="DAG Demo",
        work_dir=str(tmp_path),
        coordinator=AgentEntity(
            id="coordinator",
            name="主控智能体",
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
            system_prompt="你是主控",
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
    llm = StructuredPlanLLM()
    llm_factory = MagicMock()
    llm_factory.build.return_value = llm
    session = ChatSessionEntity(
        id="session-dag",
        title="测试会话",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )

    events = [event async for event in WorkspaceExecutor(workspace, worker_gateway, llm_factory).run("做一个页面", session)]

    task_starts = [event for event in events if event["type"] == "task_started"]
    assert [event["task_id"] for event in task_starts] == ["task-product", "task-dev"]
    assert any(event["type"] == "artifact_recorded" and event["path"] == "shared/product.md" for event in events)
    assert session.runs[0].status == "succeeded"
    assert [task.id for task in session.runs[0].tasks] == ["task-product", "task-dev"]
    assert session.runs[0].artifacts[0].path == "shared/product.md"


@pytest.mark.asyncio
async def test_workspace_executor_rejects_plan_with_unknown_worker(tmp_path):
    class BadPlanLLM(StructuredPlanLLM):
        async def astream(self, messages):
            self.seen_messages.append(messages)
            last = messages[-1].content
            if "可用 Worker" in last:
                yield SimpleNamespace(
                    content='{"tasks":[{"id":"task-1","worker_id":"missing","instruction":"做事","dependencies":[]}]}',
                    tool_calls=[],
                )
                return
            yield SimpleNamespace(content="完成", tool_calls=[])

    workspace = WorkspaceEntity(
        id="ws-bad",
        name="Bad Demo",
        work_dir=str(tmp_path),
        coordinator=AgentEntity(
            id="coordinator",
            name="主控智能体",
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
            system_prompt="你是主控",
        ),
        workers=[
            AgentEntity(
                id="worker-1",
                name="Worker",
                provider=LLMProvider.ANTHROPIC,
                model="claude-sonnet-4-6",
                system_prompt="你是 Worker",
            ),
        ],
    )
    worker_gateway = MagicMock()
    worker_gateway.list_capabilities.return_value = []
    worker_gateway.invoke = AsyncMock()
    llm_factory = MagicMock()
    llm_factory.build.return_value = BadPlanLLM()
    session = ChatSessionEntity(
        id="session-bad",
        title="测试会话",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )

    with pytest.raises(ValueError, match="不存在的 Worker"):
        _ = [event async for event in WorkspaceExecutor(workspace, worker_gateway, llm_factory).run("做一个页面", session)]

    assert session.runs[0].status == "failed"


@pytest.mark.asyncio
async def test_chat_workspace_uses_workspace_root_as_work_dir(tmp_path):
    workspace = WorkspaceEntity(
        id="ws-chat",
        name="Chat Demo",
        work_dir=str(tmp_path),
        kind=WorkspaceKind.CHAT,
        coordinator=AgentEntity(
            id="chat",
            name="单聊助手",
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
            system_prompt="你是单聊助手",
            work_subdir="chat",
        ),
        workers=[],
    )
    worker_gateway = MagicMock()
    worker_gateway.list_capabilities.return_value = []
    worker_gateway.invoke = AsyncMock()
    llm_factory = MagicMock()
    llm_factory.build.return_value = FakeLLM()

    executor = WorkspaceExecutor(workspace, worker_gateway, llm_factory)
    session = ChatSessionEntity(
        id="session-chat",
        title="测试会话",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    _ = [event async for event in executor.run("你好", session)]

    assert (tmp_path / "shared").exists()
    assert not (tmp_path / "chat").exists()
