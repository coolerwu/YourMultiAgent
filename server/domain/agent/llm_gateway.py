"""
domain/agent/llm_gateway.py

LLM 构建的抽象接口。
domain 层通过此接口获取 LLM 实例，不依赖具体 SDK。
"""

from abc import ABC, abstractmethod

from server.domain.agent.agent_entity import AgentEntity, WorkspaceEntity


class LLMGateway(ABC):
    @abstractmethod
    def build(self, agent: AgentEntity, workspace: WorkspaceEntity | None = None):
        """返回 LangChain BaseChatModel 实例"""
        ...
