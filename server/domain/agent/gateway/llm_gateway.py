"""
domain/agent/gateway/llm_gateway.py

LLM 构建的抽象接口。
domain 层通过此接口获取 LLM 实例，不依赖具体 SDK。
"""

from abc import ABC, abstractmethod

from server.domain.agent.entity.agent_entity import AgentEntity


class LLMGateway(ABC):
    @abstractmethod
    def build(self, agent: AgentEntity):
        """返回 LangChain BaseChatModel 实例"""
        ...
