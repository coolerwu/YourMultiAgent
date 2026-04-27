from unittest.mock import AsyncMock, MagicMock

import pytest

from server.adapter.settings_controller import CodexConnectionReq, GlobalSettingsReq, LLMProfileReq, update_provider_settings
from server.domain.agent.agent_entity import CodexConnectionEntity, GlobalSettingsEntity, LLMProvider, PageAuthConfigEntity


@pytest.mark.asyncio
async def test_update_provider_settings_preserves_existing_codex_runtime_fields():
    existing_settings = GlobalSettingsEntity(
        page_auth=PageAuthConfigEntity(enabled=True, access_key="ak-demo", secret_key="sk-demo"),
        codex_connections=[
            CodexConnectionEntity(
                id="codex-1",
                name="旧名称",
                status="connected",
                login_status="connected",
                account_label="ChatGPT",
                install_status="installed",
                install_path="/usr/local/bin/codex",
                last_checked_at="2026-04-09T09:00:00Z",
                last_verified_at="2026-04-09T09:00:00Z",
                cli_version="0.1.0",
            )
        ]
    )
    saved_settings = GlobalSettingsEntity(
        codex_connections=[
            CodexConnectionEntity(
                id="codex-1",
                name="新名称",
                status="connected",
                login_status="connected",
                account_label="ChatGPT",
                install_status="installed",
                install_path="/usr/local/bin/codex",
            )
        ]
    )
    workspace_svc = MagicMock()
    workspace_svc.get_global_settings = AsyncMock(return_value=existing_settings)
    workspace_svc.update_global_settings = AsyncMock(return_value=saved_settings)
    codex_runtime = MagicMock()
    codex_runtime.enrich_connections = AsyncMock(return_value=saved_settings.codex_connections)

    result = await update_provider_settings(
        GlobalSettingsReq(
            llm_profiles=[],
            codex_connections=[CodexConnectionReq(id="codex-1", name="新名称")],
        ),
        svc=workspace_svc,
        codex_runtime=codex_runtime,
    )

    saved = workspace_svc.update_global_settings.await_args.args[0]
    assert saved.codex_connections[0].name == "新名称"
    assert saved.codex_connections[0].status == "connected"
    assert saved.codex_connections[0].login_status == "connected"
    assert saved.codex_connections[0].install_status == "installed"
    assert saved.page_auth.enabled is True
    assert saved.page_auth.access_key == "ak-demo"
    assert result.codex_connections[0].login_status == "connected"


@pytest.mark.asyncio
async def test_update_provider_settings_creates_new_codex_connection_with_default_runtime_fields():
    existing_settings = GlobalSettingsEntity()
    saved_settings = GlobalSettingsEntity(
        llm_profiles=[],
        codex_connections=[CodexConnectionEntity(id="codex-2", name="新的 Codex")],
    )
    workspace_svc = MagicMock()
    workspace_svc.get_global_settings = AsyncMock(return_value=existing_settings)
    workspace_svc.update_global_settings = AsyncMock(return_value=saved_settings)
    codex_runtime = MagicMock()
    codex_runtime.enrich_connections = AsyncMock(return_value=saved_settings.codex_connections)

    await update_provider_settings(
        GlobalSettingsReq(
            llm_profiles=[
                LLMProfileReq(
                    id="llm-1",
                    name="共享 GPT",
                    provider=LLMProvider.OPENAI,
                    model="gpt-4o",
                )
            ],
            codex_connections=[CodexConnectionReq(id="codex-2", name="新的 Codex")],
        ),
        svc=workspace_svc,
        codex_runtime=codex_runtime,
    )

    saved = workspace_svc.update_global_settings.await_args.args[0]
    assert saved.llm_profiles[0].model == "gpt-4o"
    assert saved.codex_connections[0].name == "新的 Codex"
    assert saved.codex_connections[0].status == "disconnected"
    assert saved.codex_connections[0].login_status == "unknown"
