"""
infra/store/memory_agent_store.py

AgentGateway 的内存实现。
重启后数据丢失，适合初期开发阶段。
"""

from typing import Optional

from server.domain.agent.agent_entity import GraphEntity
from server.domain.agent.agent_gateway import AgentGateway


class MemoryAgentStore(AgentGateway):
    def __init__(self) -> None:
        self._store: dict[str, GraphEntity] = {}

    async def save(self, graph: GraphEntity) -> None:
        self._store[graph.id] = graph

    async def find_by_id(self, graph_id: str) -> Optional[GraphEntity]:
        return self._store.get(graph_id)

    async def find_all(self) -> list[GraphEntity]:
        return list(self._store.values())

    async def delete(self, graph_id: str) -> bool:
        if graph_id in self._store:
            del self._store[graph_id]
            return True
        return False
