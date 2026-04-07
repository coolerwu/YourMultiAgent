"""
infra/store/json_workspace_store.py

WorkspaceGateway 的文件实现。
全局索引位于 {data_dir}/setting.json；
每个 workspace 的完整配置位于 {data_dir}/workspaces/<dir_name>/workspace.json。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from server.domain.agent.entity.agent_entity import WorkspaceEntity
from server.domain.agent.gateway.workspace_gateway import WorkspaceGateway
from server.infra.store.workspace_json import (
    graphs_from_payload,
    load_setting_entries,
    load_workspace_payload,
    sanitize_workspace_name,
    save_setting_entries,
    save_workspace_payload,
    workspace_file_path,
    workspace_from_payload,
    workspace_to_payload,
)


class JsonWorkspaceStore(WorkspaceGateway):
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._migrate_legacy_if_needed()

    async def save(self, ws: WorkspaceEntity) -> None:
        entries = load_setting_entries(self._data_dir)
        entry = next((item for item in entries if item["id"] == ws.id), None)
        if entry is None:
            dir_name = _unique_dir_name(self._data_dir, sanitize_workspace_name(ws.name), entries)
            entry = {"id": ws.id, "name": ws.name, "dir_name": dir_name}
            entries.append(entry)
        else:
            entry["name"] = ws.name

        ws.dir_name = entry["dir_name"]
        payload_path = workspace_file_path(self._data_dir, entry["dir_name"])
        current_payload = load_workspace_payload(payload_path)
        current_graphs = graphs_from_payload(current_payload)
        save_workspace_payload(payload_path, workspace_to_payload(ws, current_graphs))
        save_setting_entries(self._data_dir, entries)

    async def find_by_id(self, ws_id: str) -> Optional[WorkspaceEntity]:
        entries = load_setting_entries(self._data_dir)
        entry = next((item for item in entries if item["id"] == ws_id), None)
        if entry is None:
            return None

        payload = load_workspace_payload(workspace_file_path(self._data_dir, entry["dir_name"]))
        if not payload:
            return None
        ws = workspace_from_payload(payload)
        ws.dir_name = entry["dir_name"]
        return ws

    async def find_all(self) -> list[WorkspaceEntity]:
        result: list[WorkspaceEntity] = []
        for entry in load_setting_entries(self._data_dir):
            payload = load_workspace_payload(workspace_file_path(self._data_dir, entry["dir_name"]))
            if payload:
                ws = workspace_from_payload(payload)
                ws.dir_name = entry["dir_name"]
                result.append(ws)
        return result

    async def delete(self, ws_id: str) -> bool:
        entries = load_setting_entries(self._data_dir)
        filtered = [item for item in entries if item["id"] != ws_id]
        if len(filtered) == len(entries):
            return False
        save_setting_entries(self._data_dir, filtered)
        return True

    def _migrate_legacy_if_needed(self) -> None:
        setting_file = self._data_dir / "setting.json"
        legacy_workspace_file = self._data_dir / "workspaces.json"
        legacy_graphs_file = self._data_dir / "graphs.json"
        if setting_file.exists():
            return
        if not legacy_workspace_file.exists():
            return

        try:
            old_workspaces = json.loads(legacy_workspace_file.read_text(encoding="utf-8"))
        except Exception:
            old_workspaces = {}
        try:
            old_graphs = json.loads(legacy_graphs_file.read_text(encoding="utf-8")) if legacy_graphs_file.exists() else {}
        except Exception:
            old_graphs = {}

        entries: list[dict] = []
        used_names: set[str] = set()
        graphs_by_workspace: dict[str, list[dict]] = {}
        for graph in old_graphs.values():
            workspace_id = graph.get("workspace_id", "")
            if not workspace_id:
                continue
            graphs_by_workspace.setdefault(workspace_id, []).append(graph)

        for ws_id, ws_payload in old_workspaces.items():
            dir_name = sanitize_workspace_name(ws_payload.get("name", "workspace"))
            suffix = 2
            base_name = dir_name
            while dir_name in used_names:
                dir_name = f"{base_name}-{suffix}"
                suffix += 1
            used_names.add(dir_name)
            entries.append({"id": ws_id, "name": ws_payload["name"], "dir_name": dir_name})
            workspace_payload = {
                **ws_payload,
                "dir_name": dir_name,
                "graphs": graphs_by_workspace.get(ws_id, []),
            }
            save_workspace_payload(
                workspace_file_path(self._data_dir, dir_name),
                workspace_payload,
            )

        save_setting_entries(self._data_dir, entries)


def _unique_dir_name(data_dir: Path, desired: str, entries: list[dict]) -> str:
    used = {item["dir_name"] for item in entries}
    if desired not in used:
        return desired
    index = 2
    while True:
        candidate = f"{desired}-{index}"
        if candidate not in used and not workspace_file_path(data_dir, candidate).exists():
            return candidate
        index += 1
