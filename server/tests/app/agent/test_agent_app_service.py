"""
tests/app/agent/test_agent_app_service.py

AgentAppService 单测：mock orchestrator / workspace gateway / llm gateway。
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

import server.app.agent.agent_app_service as agent_app_service_module
from server.app.agent.agent_app_service import AgentAppService
from server.app.agent.command.generate_worker_cmd import GenerateWorkerCmd
from server.app.agent.command.optimize_prompt_cmd import OptimizePromptCmd
from server.domain.agent.entity.agent_entity import AgentEntity, ChatSessionEntity, LLMProfileEntity, LLMProvider, WorkspaceEntity, WorkspaceKind


@pytest.fixture
def mock_orchestrator():
    orchestrator = MagicMock()

    async def _run(_workspace, _user_message, _session):
        yield {"type": "plan_created"}
        yield {"type": "text", "node": "coordinator", "actor_id": "coordinator", "actor_name": "主控", "content": "规划完成"}
        yield {"type": "coordinator_end", "node": "coordinator"}
        yield {"type": "run_summary", "actor_id": "coordinator", "actor_name": "主控", "summary": "已完成总结"}
        yield {"type": "done"}

    orchestrator.run = _run
    return orchestrator


@pytest.fixture
def mock_llm_gateway():
    return MagicMock()


@pytest.fixture
def mock_workspace_gateway():
    gw = AsyncMock()
    gw.find_by_id.return_value = None
    return gw


@pytest.fixture
def svc(mock_orchestrator, mock_llm_gateway, mock_workspace_gateway):
    return AgentAppService(mock_orchestrator, mock_llm_gateway, mock_workspace_gateway)


@pytest.mark.asyncio
async def test_run_workspace_not_found_raises(svc):
    async def collect():
        async for _ in svc.run_workspace("bad-id", "hello"):
            pass

    with pytest.raises(ValueError, match="Workspace 不存在"):
        await collect()


@pytest.mark.asyncio
async def test_run_workspace_streams_orchestrator_events(svc, mock_workspace_gateway):
    workspace = WorkspaceEntity(
        id="ws1",
        name="Demo",
        work_dir="/tmp/demo",
        coordinator=AgentEntity(
            id="coordinator",
            name="主控",
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
            system_prompt="你是主控。",
        ),
    )
    mock_workspace_gateway.find_by_id.return_value = workspace

    events = [event async for event in svc.run_workspace("ws1", "hello")]

    assert events[-1]["type"] == "done"
    assert any(event["type"] == "session_created" for event in events)
    assert any(event["type"] == "session_updated" for event in events)


@pytest.mark.asyncio
async def test_run_workspace_reuses_existing_session(svc, mock_workspace_gateway):
    session = ChatSessionEntity(
        id="session-1",
        title="历史会话",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    workspace = WorkspaceEntity(
        id="ws1",
        name="Demo",
        work_dir="/tmp/demo",
        sessions=[session],
        coordinator=AgentEntity(
            id="coordinator",
            name="主控",
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
            system_prompt="你是主控。",
        ),
    )
    mock_workspace_gateway.find_by_id.return_value = workspace

    events = [event async for event in svc.run_workspace("ws1", "继续", "session-1")]

    assert all(event["type"] != "session_created" for event in events)
    assert session.message_count >= 3


@pytest.mark.asyncio
async def test_run_chat_workspace_keeps_chat_kind_and_updates_session(svc, mock_workspace_gateway):
    workspace = WorkspaceEntity(
        id="chat-1",
        name="PetTrace",
        kind=WorkspaceKind.CHAT,
        work_dir="/tmp/pettrace",
        coordinator=AgentEntity(
            id="chat",
            name="单聊助手",
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
            system_prompt="你是单聊助手。",
        ),
    )
    mock_workspace_gateway.find_by_id.return_value = workspace

    events = [event async for event in svc.run_workspace("chat-1", "你好")]

    assert events[-1]["type"] == "done"
    assert any(event["type"] == "session_created" for event in events)
    assert workspace.sessions[0].message_count >= 2


@pytest.mark.asyncio
async def test_run_workspace_uses_llm_compact_for_long_session(svc, mock_workspace_gateway, mock_llm_gateway):
    from server.domain.agent.service.session_history import append_session_message

    session = ChatSessionEntity(
        id="session-1",
        title="历史会话",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    for index in range(25):
        append_session_message(session, role="user", kind="user", content=f"历史消息 {index}")

    workspace = WorkspaceEntity(
        id="ws1",
        name="Demo",
        work_dir="/tmp/demo",
        sessions=[session],
        coordinator=AgentEntity(
            id="coordinator",
            name="主控",
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
            system_prompt="你是主控。",
        ),
    )
    mock_workspace_gateway.find_by_id.return_value = workspace
    llm = AsyncMock()
    llm.ainvoke.return_value = MagicMock(
        content="【用户目标】\n继续推进\n【已完成】\n已有历史\n【关键约束】\n无\n【重要文件】\n无\n【待继续】\n继续回答"
    )
    mock_llm_gateway.build.return_value = llm

    events = [event async for event in svc.run_workspace("ws1", "继续", "session-1")]

    assert events[-1]["type"] == "done"
    assert "【用户目标】" in session.summary
    assert mock_llm_gateway.build.called


@pytest.mark.asyncio
async def test_run_workspace_persists_error_message_when_orchestrator_fails(mock_llm_gateway, mock_workspace_gateway):
    orchestrator = MagicMock()

    async def _run(_workspace, _user_message, _session):
        raise RuntimeError("执行异常: 模型调用失败")
        yield  # pragma: no cover

    orchestrator.run = _run
    svc = AgentAppService(orchestrator, mock_llm_gateway, mock_workspace_gateway)

    workspace = WorkspaceEntity(
        id="ws1",
        name="Demo",
        work_dir="/tmp/demo",
        coordinator=AgentEntity(
            id="coordinator",
            name="主控",
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
            system_prompt="你是主控。",
        ),
    )
    mock_workspace_gateway.find_by_id.return_value = workspace

    async def collect():
        return [event async for event in svc.run_workspace("ws1", "继续执行")]

    with pytest.raises(RuntimeError, match="模型调用失败"):
        await collect()

    session = workspace.sessions[0]
    assert session.status == "failed"
    assert session.messages[-1].role == "error"
    assert session.messages[-1].kind == "error"
    assert session.messages[-1].content == "执行异常: 模型调用失败"


@pytest.mark.asyncio
async def test_run_workspace_fails_when_orchestrator_idle_timeout(monkeypatch, mock_llm_gateway, mock_workspace_gateway):
    orchestrator = MagicMock()

    async def _run(_workspace, _user_message, _session):
        yield {"type": "coordinator_start", "node": "coordinator", "node_name": "主控", "actor_id": "coordinator", "actor_name": "主控"}
        await asyncio.sleep(3600)

    orchestrator.run = _run
    svc = AgentAppService(orchestrator, mock_llm_gateway, mock_workspace_gateway)

    workspace = WorkspaceEntity(
        id="ws1",
        name="Demo",
        work_dir="/tmp/demo",
        coordinator=AgentEntity(
            id="coordinator",
            name="主控",
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
            system_prompt="你是主控。",
        ),
    )
    mock_workspace_gateway.find_by_id.return_value = workspace
    monkeypatch.setattr(agent_app_service_module, "_RUN_EVENT_IDLE_TIMEOUT_SECONDS", 0.01)

    async def collect():
        return [event async for event in svc.run_workspace("ws1", "继续执行")]

    with pytest.raises(ValueError, match="执行超时"):
        await collect()

    session = workspace.sessions[0]
    assert session.status == "failed"
    assert session.messages[-1].role == "error"
    assert "执行超时" in session.messages[-1].content


@pytest.mark.asyncio
async def test_optimize_prompt_uses_workspace_profile(svc, mock_llm_gateway, mock_workspace_gateway):
    workspace = WorkspaceEntity(
        id="ws1",
        name="Demo",
        work_dir="/tmp/demo",
        llm_profiles=[
            LLMProfileEntity(
                id="profile-1",
                name="Claude",
                provider=LLMProvider.ANTHROPIC,
                model="claude-sonnet-4-6",
            )
        ],
    )
    mock_workspace_gateway.find_by_id.return_value = workspace
    llm = AsyncMock()
    llm.ainvoke.return_value = MagicMock(content='{"optimized_prompt":"新的 Prompt","reason":"更清晰。"}')
    mock_llm_gateway.build.return_value = llm

    result = await svc.optimize_prompt(
        OptimizePromptCmd(
            name="Writer",
            system_prompt="你是助手",
            workspace_id="ws1",
            llm_profile_id="profile-1",
        )
    )

    assert result["optimized_prompt"] == "新的 Prompt"
    assert result["reason"] == "更清晰。"
    mock_workspace_gateway.find_by_id.assert_awaited_once_with("ws1")


@pytest.mark.asyncio
async def test_optimize_prompt_falls_back_to_plain_text_when_json_invalid(svc, mock_llm_gateway):
    llm = AsyncMock()
    llm.ainvoke.return_value = MagicMock(content="直接输出优化后的 Prompt")
    mock_llm_gateway.build.return_value = llm

    result = await svc.optimize_prompt(
        OptimizePromptCmd(
            name="Writer",
            system_prompt="你是助手",
        )
    )

    assert result["optimized_prompt"] == "直接输出优化后的 Prompt"
    assert "回退" in result["reason"]


@pytest.mark.asyncio
async def test_optimize_edge_prompt_passes_edge_context(svc, mock_llm_gateway):
    llm = AsyncMock()
    llm.ainvoke.return_value = MagicMock(
        content='{"optimized_prompt":"请基于 report.md 继续整理摘要。","reason":"补充了下游动作和输入来源。"}'
    )
    mock_llm_gateway.build.return_value = llm

    result = await svc.optimize_prompt(
        OptimizePromptCmd(
            name="Writer",
            system_prompt="继续处理",
            prompt_kind="edge_prompt",
            source_name="Planner",
            target_name="Writer",
            artifact="report.md",
        )
    )

    assert result["optimized_prompt"] == "请基于 report.md 继续整理摘要。"
    sent_messages = llm.ainvoke.await_args.args[0]
    assert "Prompt 类型：连线 Prompt" in sent_messages[1].content
    assert "上游节点：Planner" in sent_messages[1].content


@pytest.mark.asyncio
async def test_generate_worker_filters_unknown_tools(svc, mock_llm_gateway):
    llm = AsyncMock()
    llm.ainvoke.return_value = MagicMock(
        content='{"workers":[{"name":"前端研发","system_prompt":"你负责页面实现。","work_subdir":"frontend","tools":["write_file","bad_tool"]},{"name":"测试","system_prompt":"你负责测试验证。","work_subdir":"qa","tools":["run_command"]}],"reason":"适合负责实现与验证。"}'
    )
    mock_llm_gateway.build.return_value = llm

    result = await svc.generate_worker(
        GenerateWorkerCmd(
            user_goal="需要一个前端研发 Worker",
            available_tools=["write_file", "run_command"],
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
        )
    )

    assert len(result["workers"]) == 2
    assert result["workers"][0]["name"] == "前端研发"
    assert result["workers"][0]["work_subdir"] == "frontend"
    assert result["workers"][0]["tools"] == ["write_file"]
    assert result["workers"][1]["name"] == "测试"
    assert result["workers"][1]["tools"] == ["run_command"]
    assert result["reason"] == "适合负责实现与验证。"
