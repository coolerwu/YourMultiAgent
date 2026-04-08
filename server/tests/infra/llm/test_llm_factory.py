import pytest

from server.domain.agent.entity.agent_entity import AgentEntity, CodexConnectionEntity, LLMProvider, WorkspaceEntity
from server.infra.llm.codex_cli_adapter import CodexCLIAdapter
from server.infra.llm.llm_factory import LangChainLLMFactory, _resolve_llm_config


def test_llm_factory_builds_codex_adapter(monkeypatch):
    factory = LangChainLLMFactory()
    workspace = WorkspaceEntity(
        id="ws-1",
        name="demo",
        work_dir="/tmp/demo",
        codex_connections=[
            CodexConnectionEntity(
                id="codex-1",
                name="个人 Codex",
                install_path="/usr/local/bin/codex",
            )
        ],
    )
    agent = AgentEntity(
        id="agent-1",
        name="主控",
        provider=LLMProvider.ANTHROPIC,
        model="gpt-5",
        system_prompt="你是主控",
        codex_connection_id="codex-1",
    )

    monkeypatch.setattr("server.infra.llm.llm_factory.detect_codex_path", lambda: "/usr/local/bin/codex")
    monkeypatch.setattr("server.infra.llm.llm_factory.detect_login_status", lambda _path: ("connected", "Logged in"))

    llm = factory.build(agent, workspace)

    assert isinstance(llm, CodexCLIAdapter)


def test_llm_factory_rejects_unlogged_codex(monkeypatch):
    factory = LangChainLLMFactory()
    workspace = WorkspaceEntity(
        id="ws-1",
        name="demo",
        work_dir="/tmp/demo",
        codex_connections=[
            CodexConnectionEntity(
                id="codex-1",
                name="个人 Codex",
                install_path="/usr/local/bin/codex",
            )
        ],
    )
    agent = AgentEntity(
        id="agent-1",
        name="主控",
        provider=LLMProvider.ANTHROPIC,
        model="gpt-5",
        system_prompt="你是主控",
        codex_connection_id="codex-1",
    )

    monkeypatch.setattr("server.infra.llm.llm_factory.detect_codex_path", lambda: "/usr/local/bin/codex")
    monkeypatch.setattr("server.infra.llm.llm_factory.detect_login_status", lambda _path: ("disconnected", "Not logged in"))

    with pytest.raises(ValueError, match="尚未完成 codex login"):
        factory.build(agent, workspace)


def test_resolve_llm_config_falls_back_to_workspace_defaults():
    workspace = WorkspaceEntity(
        id="ws-1",
        name="demo",
        work_dir="/tmp/demo",
        default_provider=LLMProvider.OPENAI_COMPAT,
        default_model="deepseek-chat",
        default_base_url="https://api.deepseek.com/v1",
        default_api_key="sk-demo",
    )
    agent = AgentEntity(
        id="agent-1",
        name="单聊助手",
        provider=LLMProvider.OPENAI_COMPAT,
        model="deepseek-chat",
        system_prompt="你是助手",
        base_url="",
        api_key="",
    )

    provider, model, base_url, api_key = _resolve_llm_config(agent, workspace)

    assert provider == LLMProvider.OPENAI_COMPAT
    assert model == "deepseek-chat"
    assert base_url == "https://api.deepseek.com/v1"
    assert api_key == "sk-demo"


def test_resolve_llm_config_defaults_codex_model_to_gpt_5_4():
    workspace = WorkspaceEntity(
        id="ws-1",
        name="demo",
        work_dir="/tmp/demo",
        codex_connections=[
            CodexConnectionEntity(
                id="codex-1",
                name="个人 Codex",
                install_path="/usr/local/bin/codex",
            )
        ],
    )
    agent = AgentEntity(
        id="agent-1",
        name="主控",
        provider=LLMProvider.ANTHROPIC,
        model="",
        system_prompt="你是主控",
        codex_connection_id="codex-1",
    )

    provider, model, base_url, api_key = _resolve_llm_config(agent, workspace)

    assert provider == LLMProvider.OPENAI_CODEX
    assert model == "gpt-5.4"
    assert base_url == "/usr/local/bin/codex"
    assert api_key == ""
