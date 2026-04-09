"""
tests/infra/store/test_json_workspace_store.py

JsonWorkspaceStore 单元测试：CRUD + 重启恢复 + enum 序列化。
"""

import json

import pytest

from server.domain.agent.agent_entity import AgentEntity, ChatMessageEntity, ChatSessionEntity, CodexConnectionEntity, GlobalSettingsEntity, LLMProfileEntity, LLMProvider, MemoryItemEntity, WorkspaceEntity, WorkspaceKind
from server.infra.store.json_workspace_store import JsonWorkspaceStore
from server.infra.store.workspace_json import setting_path, workspace_file_path


def _make_ws(ws_id="ws-1") -> WorkspaceEntity:
    return WorkspaceEntity(
        id=ws_id,
        name="My Workspace",
        work_dir="~/projects/test",
        kind=WorkspaceKind.WORKSPACE,
        default_provider=LLMProvider.OPENAI_COMPAT,
        default_model="deepseek-chat",
        default_base_url="https://api.deepseek.com/v1",
        llm_profiles=[
            LLMProfileEntity(
                id="llm-1",
                name="DeepSeek",
                provider=LLMProvider.OPENAI_COMPAT,
                model="deepseek-chat",
                base_url="https://api.deepseek.com/v1",
                api_key="sk-demo",
            )
        ],
        codex_connections=[
            CodexConnectionEntity(
                id="codex-1",
                name="个人 Codex",
                status="connected",
                account_label="demo@example.com",
            )
        ],
        coordinator=AgentEntity(
            id="coordinator",
            name="主控智能体",
            provider=LLMProvider.OPENAI_COMPAT,
            model="deepseek-chat",
            system_prompt="你是主控。",
            work_subdir="coordinator",
        ),
        workers=[
            AgentEntity(
                id="worker-1",
                name="研发",
                provider=LLMProvider.OPENAI_COMPAT,
                model="deepseek-chat",
                system_prompt="你是研发。",
                work_subdir="developer",
                order=2,
            ),
            AgentEntity(
                id="worker-2",
                name="测试",
                provider=LLMProvider.OPENAI_COMPAT,
                model="deepseek-chat",
                system_prompt="你是测试。",
                work_subdir="qa",
                order=1,
            )
        ],
        sessions=[
            ChatSessionEntity(
                id="session-1",
                title="历史任务",
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00",
                message_count=2,
                summary="此前完成了需求分析。",
                memory_items=[
                    MemoryItemEntity(
                        id="memory-1",
                        category="goal",
                        content="实现页面功能",
                        confidence=0.9,
                        source_message_ids=["msg-1"],
                        updated_at="2026-01-01T00:00:00+00:00",
                    )
                ],
                messages=[
                    ChatMessageEntity(
                        id="msg-1",
                        role="user",
                        kind="user",
                        content="做一个页面",
                        created_at="2026-01-01T00:00:00+00:00",
                    ),
                    ChatMessageEntity(
                        id="msg-2",
                        role="assistant",
                        kind="summary",
                        content="需求已拆解",
                        created_at="2026-01-01T00:01:00+00:00",
                        actor_name="主控智能体",
                    ),
                ],
            )
        ],
    )


@pytest.mark.asyncio
async def test_save_and_find_by_id(tmp_path):
    store = JsonWorkspaceStore(tmp_path)
    await store.save_global_settings(
        GlobalSettingsEntity(
            llm_profiles=[
                LLMProfileEntity(
                    id="llm-1",
                    name="DeepSeek",
                    provider=LLMProvider.OPENAI_COMPAT,
                    model="deepseek-chat",
                    base_url="https://api.deepseek.com/v1",
                    api_key="sk-demo",
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
    )
    await store.save(_make_ws())
    result = await store.find_by_id("ws-1")
    assert result is not None
    assert result.name == "My Workspace"
    assert result.dir_name == "My-Workspace"
    assert result.kind == WorkspaceKind.WORKSPACE
    assert setting_path(tmp_path).exists()
    assert workspace_file_path(tmp_path, "My-Workspace").exists()


@pytest.mark.asyncio
async def test_enum_roundtrip(tmp_path):
    store = JsonWorkspaceStore(tmp_path)
    await store.save_global_settings(
        GlobalSettingsEntity(
            llm_profiles=[
                LLMProfileEntity(
                    id="llm-1",
                    name="DeepSeek",
                    provider=LLMProvider.OPENAI_COMPAT,
                    model="deepseek-chat",
                    base_url="https://api.deepseek.com/v1",
                    api_key="sk-demo",
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
    )
    await store.save(_make_ws())

    store2 = JsonWorkspaceStore(tmp_path)
    result = await store2.find_by_id("ws-1")
    assert result.llm_profiles[0].name == "DeepSeek"
    assert result.codex_connections[0].name == "个人 Codex"
    assert result.coordinator.name == "主控智能体"
    assert result.workers[0].name == "研发"
    assert result.workers[0].order == 2
    assert result.workers[1].name == "测试"
    assert result.workers[1].order == 1
    assert result.sessions[0].title == "历史任务"
    assert result.sessions[0].memory_items[0].content == "实现页面功能"


@pytest.mark.asyncio
async def test_data_persists(tmp_path):
    store1 = JsonWorkspaceStore(tmp_path)
    await store1.save_global_settings(GlobalSettingsEntity())
    await store1.save(_make_ws("ws-persist"))

    store2 = JsonWorkspaceStore(tmp_path)
    result = await store2.find_by_id("ws-persist")
    assert result is not None


@pytest.mark.asyncio
async def test_find_all_empty(tmp_path):
    store = JsonWorkspaceStore(tmp_path)
    assert await store.find_all() == []


@pytest.mark.asyncio
async def test_delete(tmp_path):
    store = JsonWorkspaceStore(tmp_path)
    await store.save_global_settings(GlobalSettingsEntity())
    await store.save(_make_ws())
    ok = await store.delete("ws-1")
    assert ok is True
    assert await store.find_by_id("ws-1") is None


@pytest.mark.asyncio
async def test_delete_nonexistent(tmp_path):
    store = JsonWorkspaceStore(tmp_path)
    assert await store.delete("ghost") is False


@pytest.mark.asyncio
async def test_save_chat_workspace_preserves_kind_and_custom_dir(tmp_path):
    store = JsonWorkspaceStore(tmp_path)
    await store.save_global_settings(GlobalSettingsEntity())
    workspace = _make_ws("chat-1")
    workspace.kind = WorkspaceKind.CHAT
    workspace.dir_name = "pettrace"
    workspace.work_dir = str(tmp_path / "workspaces" / "pettrace")

    await store.save(workspace)
    result = await store.find_by_id("chat-1")

    assert result is not None
    assert result.kind == WorkspaceKind.CHAT
    assert result.dir_name == "pettrace"
    assert workspace_file_path(tmp_path, "pettrace").exists()


@pytest.mark.asyncio
async def test_migrates_legacy_global_json_files(tmp_path):
    legacy_workspaces = {
        "ws-1": {
            "id": "ws-1",
            "name": "Legacy WS",
            "work_dir": "/tmp/legacy",
            "default_provider": "anthropic",
            "default_model": "claude-sonnet-4-6",
            "default_base_url": "",
            "default_api_key": "",
            "llm_profiles": [],
        }
    }
    legacy_graphs = {
        "g-1": {
            "id": "g-1",
            "name": "Legacy Graph",
            "entry_node": "a1",
            "workspace_id": "ws-1",
            "agents": [],
            "edges": [],
        }
    }
    (tmp_path / "workspaces.json").write_text(__import__("json").dumps(legacy_workspaces), encoding="utf-8")
    (tmp_path / "graphs.json").write_text(__import__("json").dumps(legacy_graphs), encoding="utf-8")

    store = JsonWorkspaceStore(tmp_path)
    result = await store.find_by_id("ws-1")

    assert result is not None
    assert result.name == "Legacy WS"
    payload = json.loads(workspace_file_path(tmp_path, "Legacy-WS").read_text(encoding="utf-8"))
    assert payload["graphs"][0]["name"] == "Legacy Graph"
    settings_payload = json.loads(setting_path(tmp_path).read_text(encoding="utf-8"))
    assert settings_payload["global_settings"]["llm_profiles"] == []


@pytest.mark.asyncio
async def test_setting_json_persists_global_provider_settings(tmp_path):
    store = JsonWorkspaceStore(tmp_path)
    saved = await store.save_global_settings(
        GlobalSettingsEntity(
            llm_profiles=[
                LLMProfileEntity(
                    id="llm-1",
                    name="共享 GPT",
                    provider=LLMProvider.OPENAI,
                    model="gpt-4o-mini",
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
    )

    loaded = await store.load_global_settings()

    assert loaded.llm_profiles[0].name == "共享 GPT"
    assert loaded.codex_connections[0].name == "个人 Codex"
    payload = json.loads(setting_path(tmp_path).read_text(encoding="utf-8"))
    assert payload["global_settings"]["llm_profiles"][0]["model"] == "gpt-4o-mini"
    assert payload["global_settings"]["codex_connections"][0]["name"] == "个人 Codex"
