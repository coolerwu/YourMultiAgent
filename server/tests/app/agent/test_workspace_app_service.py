"""
tests/app/agent/test_workspace_app_service.py

WorkspaceAppService 单元测试：覆盖 CRUD 正常路径 + 边界 case。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from server.app.agent.workspace_app_service import (
    CreateWorkspaceCmd,
    LLMProfileCmd,
    UpdateWorkspaceOrchestrationCmd,
    UpdateWorkspaceCmd,
    WorkspaceAppService,
)
from server.app.agent.command.create_agent_cmd import AgentNodeCmd
from server.domain.agent.agent_entity import CodexConnectionEntity, GlobalSettingsEntity, LLMProfileEntity, LLMProvider, WorkspaceEntity
from server.domain.agent.agent_entity import WorkspaceKind


def _make_gateway(ws: WorkspaceEntity | None = None):
    gw = MagicMock()
    gw.save = AsyncMock()
    gw.find_by_id = AsyncMock(return_value=ws)
    gw.find_all = AsyncMock(return_value=[] if ws is None else [ws])
    gw.delete = AsyncMock(return_value=True)
    gw.load_global_settings = AsyncMock(return_value=GlobalSettingsEntity())
    gw.save_global_settings = AsyncMock(side_effect=lambda settings: settings)
    return gw


def _sample_create_cmd() -> CreateWorkspaceCmd:
    return CreateWorkspaceCmd(
        name="My WS",
        work_dir="~/projects",
        default_provider=LLMProvider.OPENAI,
        default_model="gpt-4o",
        llm_profiles=[
            LLMProfileCmd(
                id="llm-1",
                name="共享 GPT",
                provider=LLMProvider.OPENAI,
                model="gpt-4o-mini",
            )
        ],
    )


@pytest.mark.asyncio
async def test_create_workspace_calls_save():
    gw = _make_gateway()
    gw.load_global_settings.return_value = GlobalSettingsEntity(
        llm_profiles=[
            LLMProfileEntity(
                id="llm-1",
                name="共享 GPT",
                provider=LLMProvider.OPENAI,
                model="gpt-4o-mini",
            )
        ],
    )
    svc = WorkspaceAppService(gw)
    ws = await svc.create_workspace(_sample_create_cmd())
    gw.save.assert_awaited_once()
    assert ws.name == "My WS"
    assert ws.llm_profiles[0].name == "共享 GPT"
    assert ws.coordinator is not None
    assert ws.coordinator.name == "主控智能体"
    assert ws.coordinator.llm_profile_id == "llm-1"
    assert ws.kind == WorkspaceKind.WORKSPACE


@pytest.mark.asyncio
async def test_create_workspace_uses_default_work_dir_when_empty():
    gw = _make_gateway()
    gw.load_global_settings.return_value = GlobalSettingsEntity(
        llm_profiles=[
            LLMProfileEntity(
                id="llm-1",
                name="共享 GPT",
                provider=LLMProvider.OPENAI,
                model="gpt-4o-mini",
            )
        ],
    )
    svc = WorkspaceAppService(gw)
    cmd = _sample_create_cmd()
    cmd.work_dir = ""
    ws = await svc.create_workspace(cmd)
    assert ws.work_dir.endswith("/workspaces/My-WS") or ws.work_dir.endswith("\\workspaces\\My-WS")


@pytest.mark.asyncio
async def test_create_chat_workspace_uses_dir_name_and_chat_agent():
    gw = _make_gateway()
    gw.load_global_settings.return_value = GlobalSettingsEntity(
        llm_profiles=[
            LLMProfileEntity(
                id="llm-1",
                name="共享 GPT",
                provider=LLMProvider.OPENAI,
                model="gpt-4o-mini",
            )
        ],
    )
    svc = WorkspaceAppService(gw)
    cmd = _sample_create_cmd()
    cmd.kind = WorkspaceKind.CHAT
    cmd.dir_name = "pettrace"
    cmd.work_dir = ""

    ws = await svc.create_workspace(cmd)

    assert ws.kind == WorkspaceKind.CHAT
    assert ws.dir_name == "pettrace"
    assert ws.work_dir.endswith("/workspaces/pettrace") or ws.work_dir.endswith("\\workspaces\\pettrace")
    assert ws.coordinator is not None
    assert ws.coordinator.name == "单聊助手"
    assert ws.coordinator.work_subdir == ""
    assert ws.coordinator.llm_profile_id == "llm-1"


@pytest.mark.asyncio
async def test_create_workspace_generates_id():
    gw = _make_gateway()
    gw.load_global_settings.return_value = GlobalSettingsEntity(
        llm_profiles=[
            LLMProfileEntity(
                id="llm-1",
                name="共享 GPT",
                provider=LLMProvider.OPENAI,
                model="gpt-4o-mini",
            )
        ],
    )
    svc = WorkspaceAppService(gw)
    ws1 = await svc.create_workspace(_sample_create_cmd())
    ws2 = await svc.create_workspace(_sample_create_cmd())
    assert ws1.id != ws2.id


@pytest.mark.asyncio
async def test_update_workspace():
    existing = WorkspaceEntity(id="ws-42", name="Old", work_dir="~/old")
    gw = _make_gateway(existing)
    gw.load_global_settings.return_value = GlobalSettingsEntity(
        llm_profiles=[
            LLMProfileEntity(
                id="llm-1",
                name="共享 GPT",
                provider=LLMProvider.OPENAI,
                model="gpt-4o-mini",
            )
        ],
    )
    svc = WorkspaceAppService(gw)
    cmd = UpdateWorkspaceCmd(
        workspace_id="ws-42",
        name="Updated",
        work_dir="~/new",
        default_provider=LLMProvider.ANTHROPIC,
        default_model="claude-3-5-sonnet",
    )
    ws = await svc.update_workspace(cmd)
    assert ws.id == "ws-42"
    assert ws.name == "Updated"
    assert ws.coordinator == existing.coordinator
    gw.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_orchestration_updates_coordinator_and_workers():
    existing = WorkspaceEntity(
        id="ws-42",
        name="Old",
        work_dir="~/old",
        default_provider=LLMProvider.OPENAI_COMPAT,
        default_model="deepseek-reasoner",
        default_base_url="https://api.deepseek.com/v1",
        llm_profiles=[
            LLMProfileEntity(
                id="profile-1",
                name="Claude 主力",
                provider=LLMProvider.ANTHROPIC,
                model="claude-sonnet-4-6",
            ),
            LLMProfileEntity(
                id="profile-2",
                name="GPT 主力",
                provider=LLMProvider.OPENAI,
                model="gpt-4o",
            ),
        ],
    )
    gw = _make_gateway(existing)
    svc = WorkspaceAppService(gw)

    updated = await svc.update_orchestration(
        UpdateWorkspaceOrchestrationCmd(
            workspace_id="ws-42",
            coordinator=AgentNodeCmd(
                id="coordinator",
                name="主控",
                provider=LLMProvider.ANTHROPIC,
                model="claude-sonnet-4-6",
                system_prompt="你是主控",
                llm_profile_id="profile-1",
            ),
            workers=[
                AgentNodeCmd(
                    id="worker-1",
                    name="研发",
                    provider=LLMProvider.OPENAI,
                    model="gpt-4o",
                    system_prompt="你是研发",
                    llm_profile_id="profile-2",
                    order=2,
                ),
                AgentNodeCmd(
                    id="worker-2",
                    name="测试",
                    provider=LLMProvider.OPENAI,
                    model="gpt-4o-mini",
                    system_prompt="你是测试",
                    llm_profile_id="profile-2",
                    order=1,
                )
            ],
        )
    )

    assert updated.coordinator.name == "主控"
    assert updated.coordinator.llm_profile_id == "profile-1"
    assert updated.workers[0].name == "测试"
    assert updated.workers[0].order == 1
    assert updated.workers[0].llm_profile_id == "profile-2"
    assert updated.workers[1].name == "研发"
    assert updated.workers[1].order == 2


@pytest.mark.asyncio
async def test_update_orchestration_normalizes_legacy_llm_and_codex_fields():
    existing = WorkspaceEntity(
        id="ws-legacy",
        name="Legacy",
        work_dir="~/legacy",
        default_provider=LLMProvider.OPENAI_COMPAT,
        default_model="deepseek-reasoner",
        default_base_url="https://api.deepseek.com/v1",
    )
    gw = _make_gateway(existing)
    svc = WorkspaceAppService(gw)

    updated = await svc.update_orchestration(
        UpdateWorkspaceOrchestrationCmd(
            workspace_id="ws-legacy",
            coordinator=AgentNodeCmd(
                id="chat",
                name="单聊助手",
                provider=LLMProvider.ANTHROPIC,
                model="",
                system_prompt="你是助手",
                codex_connection_id="codex-stale",
                llm_profile_id="profile-stale",
                base_url="https://wrong.example.com",
            ),
            workers=[],
        )
    )

    assert updated.coordinator.provider == LLMProvider.ANTHROPIC
    assert updated.coordinator.model == "claude-sonnet-4-6"
    assert updated.coordinator.codex_connection_id == ""
    assert updated.coordinator.llm_profile_id == ""
    assert updated.coordinator.base_url == ""


@pytest.mark.asyncio
async def test_list_workspaces_empty():
    gw = _make_gateway()
    svc = WorkspaceAppService(gw)
    result = await svc.list_workspaces()
    assert result == []


@pytest.mark.asyncio
async def test_get_workspace_not_found():
    gw = _make_gateway(ws=None)
    svc = WorkspaceAppService(gw)
    result = await svc.get_workspace("ghost")
    assert result is None


@pytest.mark.asyncio
async def test_delete_workspace_delegates():
    gw = _make_gateway()
    svc = WorkspaceAppService(gw)
    ok = await svc.delete_workspace("ws-1")
    assert ok is True
    gw.delete.assert_awaited_once_with("ws-1")


@pytest.mark.asyncio
async def test_create_and_get_session():
    existing = WorkspaceEntity(id="ws-42", name="Old", work_dir="~/old")
    gw = _make_gateway(existing)
    svc = WorkspaceAppService(gw)

    session = await svc.create_session("ws-42", "第一条任务")

    assert session.title == "第一条任务"
    assert existing.sessions[0].id == session.id
    found = await svc.get_session("ws-42", session.id)
    assert found is not None
    assert found.id == session.id


@pytest.mark.asyncio
async def test_delete_session_removes_session():
    existing = WorkspaceEntity(id="ws-42", name="Old", work_dir="~/old")
    gw = _make_gateway(existing)
    svc = WorkspaceAppService(gw)
    session = await svc.create_session("ws-42", "第一条任务")

    ok = await svc.delete_session("ws-42", session.id)

    assert ok is True
    assert existing.sessions == []


@pytest.mark.asyncio
async def test_update_global_settings_delegates_and_syncs_workspaces():
    existing = WorkspaceEntity(id="ws-42", name="Old", work_dir="~/old")
    gw = _make_gateway(existing)
    svc = WorkspaceAppService(gw)

    settings = GlobalSettingsEntity(
        llm_profiles=[
            LLMProfileEntity(
                id="llm-1",
                name="共享 GPT",
                provider=LLMProvider.OPENAI,
                model="gpt-4o",
            )
        ],
        codex_connections=[
            CodexConnectionEntity(
                id="codex-1",
                name="个人 Codex",
                status="connected",
            )
        ],
    )

    saved = await svc.update_global_settings(settings)

    assert saved.llm_profiles[0].model == "gpt-4o"
    gw.save_global_settings.assert_awaited_once()
    assert existing.default_model == "gpt-4o"
    assert existing.llm_profiles[0].name == "共享 GPT"
    assert existing.codex_connections[0].name == "个人 Codex"
