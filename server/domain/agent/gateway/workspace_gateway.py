"""
domain/agent/gateway/workspace_gateway.py

Workspace 存储的抽象接口。
"""

from abc import ABC, abstractmethod
from typing import Optional

from server.domain.agent.entity.agent_entity import WorkspaceEntity


class WorkspaceGateway(ABC):

    @abstractmethod
    async def save(self, ws: WorkspaceEntity) -> None: ...

    @abstractmethod
    async def find_by_id(self, ws_id: str) -> Optional[WorkspaceEntity]: ...

    @abstractmethod
    async def find_all(self) -> list[WorkspaceEntity]: ...

    @abstractmethod
    async def delete(self, ws_id: str) -> bool: ...
