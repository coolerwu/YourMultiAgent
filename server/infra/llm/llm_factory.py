"""
infra/llm/llm_factory.py

LLMGateway 实现：根据 AgentEntity 构建 LangChain LLM 实例。
支持 Anthropic、OpenAI、以及任意 OpenAI 兼容协议（DeepSeek/Moonshot 等）。
API Key 优先用 agent 级配置，若节点引用 workspace LLM profile 则先用 profile，再退回环境变量。
"""

from server.domain.agent.entity.agent_entity import AgentEntity, LLMProvider, WorkspaceEntity
from server.domain.agent.gateway.llm_gateway import LLMGateway
from server.infra.codex.codex_cli import detect_codex_path, detect_login_status
from server.infra.llm.codex_cli_adapter import CodexCLIAdapter


class LangChainLLMFactory(LLMGateway):
    def build(self, agent: AgentEntity, workspace: WorkspaceEntity | None = None):
        provider, model, base_url, api_key = _resolve_llm_config(agent, workspace)

        if provider == LLMProvider.ANTHROPIC:
            from langchain_anthropic import ChatAnthropic
            kwargs = dict(model=model, temperature=agent.temperature, max_tokens=agent.max_tokens)
            if api_key:
                kwargs["anthropic_api_key"] = api_key
            return ChatAnthropic(**kwargs)

        elif provider == LLMProvider.OPENAI:
            from langchain_openai import ChatOpenAI
            kwargs = dict(model=model, temperature=agent.temperature, max_tokens=agent.max_tokens)
            if api_key:
                kwargs["openai_api_key"] = api_key
            return ChatOpenAI(**kwargs)

        elif provider == LLMProvider.OPENAI_COMPAT:
            from langchain_openai import ChatOpenAI
            if not base_url:
                raise ValueError(f"Agent '{agent.name}' 使用 openai_compat 时必须配置 base_url")
            # api_key 留空时传 "sk-placeholder"，部分服务不校验 key
            compat_api_key = api_key or "sk-placeholder"
            return ChatOpenAI(
                model=model,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
                base_url=base_url,
                api_key=compat_api_key,
            )

        elif provider == LLMProvider.OPENAI_CODEX:
            codex_path = base_url or detect_codex_path()
            if not codex_path:
                raise ValueError(f"Agent '{agent.name}' 选择了 Codex，但当前宿主机未安装 codex CLI")
            login_status, _ = detect_login_status(codex_path)
            if login_status != "connected":
                raise ValueError(f"Agent '{agent.name}' 选择了 Codex，但当前宿主机尚未完成 codex login")
            return CodexCLIAdapter(
                model=model,
                codex_path=codex_path,
                work_dir=workspace.work_dir if workspace else "",
            )

        else:
            raise ValueError(f"不支持的 LLM provider: {provider}")


def _resolve_llm_config(
    agent: AgentEntity,
    workspace: WorkspaceEntity | None,
) -> tuple[LLMProvider, str, str, str]:
    if workspace and agent.codex_connection_id:
        connection = next((item for item in workspace.codex_connections if item.id == agent.codex_connection_id), None)
        if connection is None:
            raise ValueError(f"Agent '{agent.name}' 引用了不存在的 Codex 登录连接: {agent.codex_connection_id}")
        return (
            LLMProvider.OPENAI_CODEX,
            agent.model or "gpt-5",
            connection.install_path,
            "",
        )

    if workspace and agent.llm_profile_id:
        profile = next((p for p in workspace.llm_profiles if p.id == agent.llm_profile_id), None)
        if profile is None:
            raise ValueError(f"Agent '{agent.name}' 引用了不存在的 LLM 配置: {agent.llm_profile_id}")
        return (
            profile.provider,
            profile.model,
            agent.base_url or profile.base_url,
            agent.api_key or profile.api_key,
        )

    return agent.provider, agent.model, agent.base_url, agent.api_key
