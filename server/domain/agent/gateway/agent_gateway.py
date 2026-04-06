"""
domain/agent/gateway/agent_gateway.py

Agent 存储的抽象接口（Gateway 模式）。
domain 层只依赖此接口，infra 层提供具体实现。
"""

from abc import ABC, abstractmethod
from typing import Optional

from server.domain.agent.entity.agent_entity import GraphEntity


class AgentGateway(ABC):
    """Agent 图配置的存储接口"""

    @abstractmethod
    async def save(self, graph: GraphEntity) -> None: ...

    @abstractmethod
    async def find_by_id(self, graph_id: str) -> Optional[GraphEntity]: ...

    @abstractmethod
    async def find_all(self) -> list[GraphEntity]: ...

    @abstractmethod
    async def delete(self, graph_id: str) -> bool: ...
