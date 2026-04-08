"""
infra/store/memory_workspace_store.py

WorkspaceGateway 的内存实现。
"""

from typing import Optional

from server.domain.agent.entity.agent_entity import GlobalSettingsEntity, WorkspaceEntity
from server.domain.agent.gateway.workspace_gateway import WorkspaceGateway


class MemoryWorkspaceStore(WorkspaceGateway):
    def __init__(self) -> None:
        self._store: dict[str, WorkspaceEntity] = {}
        self._settings = GlobalSettingsEntity()

    async def save(self, ws: WorkspaceEntity) -> None:
        self._store[ws.id] = ws

    async def find_by_id(self, ws_id: str) -> Optional[WorkspaceEntity]:
        return self._store.get(ws_id)

    async def find_all(self) -> list[WorkspaceEntity]:
        return list(self._store.values())

    async def delete(self, ws_id: str) -> bool:
        if ws_id in self._store:
            del self._store[ws_id]
            return True
        return False

    async def load_global_settings(self) -> GlobalSettingsEntity:
        return self._settings

    async def save_global_settings(self, settings: GlobalSettingsEntity) -> GlobalSettingsEntity:
        self._settings = settings
        return self._settings
