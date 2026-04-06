"""
infra/llm/llm_factory.py

LLMGateway 的具体实现：根据 AgentEntity 配置构建 LangChain LLM 实例。
API Key 从环境变量读取：ANTHROPIC_API_KEY / OPENAI_API_KEY。
"""

from server.domain.agent.entity.agent_entity import AgentEntity, LLMProvider
from server.domain.agent.gateway.llm_gateway import LLMGateway


class LangChainLLMFactory(LLMGateway):
    def build(self, agent: AgentEntity):
        if agent.provider == LLMProvider.ANTHROPIC:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=agent.model,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
            )
        elif agent.provider == LLMProvider.OPENAI:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=agent.model,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
            )
        else:
            raise ValueError(f"不支持的 LLM provider: {agent.provider}")
