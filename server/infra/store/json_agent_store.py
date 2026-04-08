"""
infra/store/json_agent_store.py

AgentGateway 的文件实现。
所有 graph 都保存在所属 workspace 目录内的 workspace.json 中。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from server.domain.agent.agent_entity import GraphEntity
from server.domain.agent.agent_gateway import AgentGateway
from server.infra.store.workspace_json import (
    load_setting_entries,
    load_workspace_payload,
    save_workspace_payload,
    workspace_file_path,
    workspace_to_payload,
    workspace_from_payload,
    graphs_from_payload,
)


class JsonAgentStore(AgentGateway):
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    async def save(self, graph: GraphEntity) -> None:
        if not graph.workspace_id:
            raise ValueError("Graph 必须绑定 workspace_id")

        entry = self._find_workspace_entry(graph.workspace_id)
        if entry is None:
            raise ValueError(f"Workspace 不存在: {graph.workspace_id}")

        payload_path = workspace_file_path(self._data_dir, entry["dir_name"])
        payload = load_workspace_payload(payload_path)
        if not payload:
            raise ValueError(f"Workspace 配置不存在: {entry['dir_name']}")

        workspace = workspace_from_payload(payload)
        graphs = graphs_from_payload(payload)
        replaced = False
        for idx, current in enumerate(graphs):
            if current.id == graph.id:
                graphs[idx] = graph
                replaced = True
                break
        if not replaced:
            graphs.append(graph)

        save_workspace_payload(payload_path, workspace_to_payload(workspace, graphs))

    async def find_by_id(self, graph_id: str) -> Optional[GraphEntity]:
        for entry in load_setting_entries(self._data_dir):
            payload = load_workspace_payload(workspace_file_path(self._data_dir, entry["dir_name"]))
            for graph in graphs_from_payload(payload):
                if graph.id == graph_id:
                    return graph
        return None

    async def find_all(self) -> list[GraphEntity]:
        result: list[GraphEntity] = []
        for entry in load_setting_entries(self._data_dir):
            payload = load_workspace_payload(workspace_file_path(self._data_dir, entry["dir_name"]))
            result.extend(graphs_from_payload(payload))
        return result

    async def delete(self, graph_id: str) -> bool:
        for entry in load_setting_entries(self._data_dir):
            payload_path = workspace_file_path(self._data_dir, entry["dir_name"])
            payload = load_workspace_payload(payload_path)
            if not payload:
                continue
            workspace = workspace_from_payload(payload)
            graphs = graphs_from_payload(payload)
            filtered = [graph for graph in graphs if graph.id != graph_id]
            if len(filtered) != len(graphs):
                save_workspace_payload(payload_path, workspace_to_payload(workspace, filtered))
                return True
        return False

    def _find_workspace_entry(self, workspace_id: str) -> Optional[dict]:
        return next((item for item in load_setting_entries(self._data_dir) if item["id"] == workspace_id), None)
