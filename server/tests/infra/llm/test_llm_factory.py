import pytest

from server.domain.agent.agent_entity import AgentEntity, CodexConnectionEntity, LLMProfileEntity, LLMProvider, WorkspaceEntity, WorkspaceKind
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
        provider=LLMProvider.OPENAI_CODEX,
        model="gpt-5",
        system_prompt="你是主控",
        codex_connection_id="codex-1",
    )

    monkeypatch.setattr("server.infra.llm.llm_factory.detect_codex_path", lambda: "/usr/local/bin/codex")
    monkeypatch.setattr("server.infra.llm.llm_factory.detect_login_status", lambda _path: ("connected", "Logged in"))

    llm = factory.build(agent, workspace)

    assert isinstance(llm, CodexCLIAdapter)
    assert llm._simple_output_mode is False


def test_llm_factory_enables_simple_mode_for_chat_codex(monkeypatch):
    factory = LangChainLLMFactory()
    workspace = WorkspaceEntity(
        id="ws-chat",
        name="chat-demo",
        kind=WorkspaceKind.CHAT,
        work_dir="/tmp/chat-demo",
        codex_connections=[
            CodexConnectionEntity(
                id="codex-1",
                name="个人 Codex",
                install_path="/usr/local/bin/codex",
            )
        ],
    )
    agent = AgentEntity(
        id="chat",
        name="单聊助手",
        provider=LLMProvider.OPENAI_CODEX,
        model="gpt-5",
        system_prompt="你是单聊助手",
        codex_connection_id="codex-1",
    )

    monkeypatch.setattr("server.infra.llm.llm_factory.detect_codex_path", lambda: "/usr/local/bin/codex")
    monkeypatch.setattr("server.infra.llm.llm_factory.detect_login_status", lambda _path: ("connected", "Logged in"))

    llm = factory.build(agent, workspace)

    assert isinstance(llm, CodexCLIAdapter)
    assert llm._simple_output_mode is True


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
        provider=LLMProvider.OPENAI_CODEX,
        model="gpt-5",
        system_prompt="你是主控",
        codex_connection_id="codex-1",
    )

    monkeypatch.setattr("server.infra.llm.llm_factory.detect_codex_path", lambda: "/usr/local/bin/codex")
    monkeypatch.setattr("server.infra.llm.llm_factory.detect_login_status", lambda _path: ("disconnected", "Not logged in"))

    with pytest.raises(ValueError, match="尚未完成 codex login"):
        factory.build(agent, workspace)


def test_resolve_llm_config_prefers_bound_llm_profile():
    workspace = WorkspaceEntity(
        id="ws-1",
        name="demo",
        work_dir="/tmp/demo",
        llm_profiles=[
            LLMProfileEntity(
                id="profile-1",
                name="DeepSeek",
                provider=LLMProvider.OPENAI_COMPAT,
                model="deepseek-chat",
                base_url="https://api.deepseek.com/v1",
                api_key="sk-demo",
            )
        ],
    )
    agent = AgentEntity(
        id="agent-1",
        name="主控",
        provider=LLMProvider.OPENAI_COMPAT,
        model="",
        system_prompt="你是主控",
        llm_profile_id="profile-1",
        base_url="",
        api_key="",
    )

    provider, model, base_url, api_key = _resolve_llm_config(agent, workspace)

    assert provider == LLMProvider.OPENAI_COMPAT
    assert model == "deepseek-chat"
    assert base_url == "https://api.deepseek.com/v1"
    assert api_key == "sk-demo"


def test_resolve_llm_config_treats_legacy_default_codex_model_as_unset():
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
        provider=LLMProvider.OPENAI_CODEX,
        model="",
        system_prompt="你是主控",
        codex_connection_id="codex-1",
    )

    provider, model, base_url, api_key = _resolve_llm_config(agent, workspace)

    assert provider == LLMProvider.OPENAI_CODEX
    assert model == ""
    assert base_url == "/usr/local/bin/codex"
    assert api_key == ""


def test_resolve_llm_config_keeps_explicit_codex_model():
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
        provider=LLMProvider.OPENAI_CODEX,
        model="gpt-5",
        system_prompt="你是主控",
        codex_connection_id="codex-1",
    )

    provider, model, base_url, api_key = _resolve_llm_config(agent, workspace)

    assert provider == LLMProvider.OPENAI_CODEX
    assert model == "gpt-5"
    assert base_url == "/usr/local/bin/codex"
    assert api_key == ""


def test_resolve_llm_config_ignores_stale_codex_connection_when_provider_is_llm():
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
        name="单聊助手",
        provider=LLMProvider.ANTHROPIC,
        model="",
        system_prompt="你是助手",
        codex_connection_id="codex-1",
    )

    provider, model, base_url, api_key = _resolve_llm_config(agent, workspace)

    assert provider == LLMProvider.ANTHROPIC
    assert model == ""
    assert base_url == ""
    assert api_key == ""
