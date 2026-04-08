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

from server.domain.agent.agent_entity import CodexConnectionEntity, GlobalSettingsEntity, LLMProfileEntity, LLMProvider, WorkspaceEntity
from server.domain.agent.workspace_gateway import WorkspaceGateway
from server.infra.store.workspace_json import (
    graphs_from_payload,
    load_global_settings,
    load_setting_entries,
    load_workspace_payload,
    sanitize_workspace_name,
    save_global_settings,
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
            desired_dir_name = sanitize_workspace_name(ws.dir_name or ws.name)
            dir_name = _unique_dir_name(self._data_dir, desired_dir_name, entries)
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
        settings = load_global_settings(self._data_dir)
        _apply_global_settings(ws, settings)
        ws.dir_name = entry["dir_name"]
        return ws

    async def find_all(self) -> list[WorkspaceEntity]:
        result: list[WorkspaceEntity] = []
        for entry in load_setting_entries(self._data_dir):
            payload = load_workspace_payload(workspace_file_path(self._data_dir, entry["dir_name"]))
            if payload:
                ws = workspace_from_payload(payload)
                settings = load_global_settings(self._data_dir)
                _apply_global_settings(ws, settings)
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
        migrated_settings = None
        for graph in old_graphs.values():
            workspace_id = graph.get("workspace_id", "")
            if not workspace_id:
                continue
            graphs_by_workspace.setdefault(workspace_id, []).append(graph)

        for ws_id, ws_payload in old_workspaces.items():
            if migrated_settings is None:
                migrated_settings = {
                    "default_provider": ws_payload.get("default_provider", "anthropic"),
                    "default_model": ws_payload.get("default_model", "claude-sonnet-4-6"),
                    "default_base_url": ws_payload.get("default_base_url", ""),
                    "default_api_key": ws_payload.get("default_api_key", ""),
                    "llm_profiles": ws_payload.get("llm_profiles", []),
                    "codex_connections": ws_payload.get("codex_connections", []),
                }
            dir_name = sanitize_workspace_name(ws_payload.get("name", "workspace"))
            suffix = 2
            base_name = dir_name
            while dir_name in used_names:
                dir_name = f"{base_name}-{suffix}"
                suffix += 1
            used_names.add(dir_name)
            entries.append({"id": ws_id, "name": ws_payload["name"], "dir_name": dir_name})
            workspace_payload = {
                **{
                    key: value
                    for key, value in ws_payload.items()
                    if key not in {"default_provider", "default_model", "default_base_url", "default_api_key", "llm_profiles", "codex_connections"}
                },
                "dir_name": dir_name,
                "graphs": graphs_by_workspace.get(ws_id, []),
            }
            save_workspace_payload(
                workspace_file_path(self._data_dir, dir_name),
                workspace_payload,
            )

        save_setting_entries(self._data_dir, entries)
        if migrated_settings is not None:
            save_global_settings(self._data_dir, _global_settings_from_legacy(migrated_settings))

    async def load_global_settings(self) -> GlobalSettingsEntity:
        return load_global_settings(self._data_dir)

    async def save_global_settings(self, settings: GlobalSettingsEntity) -> GlobalSettingsEntity:
        save_global_settings(self._data_dir, settings)
        return settings


def _apply_global_settings(ws: WorkspaceEntity, settings: GlobalSettingsEntity) -> None:
    ws.default_provider = settings.default_provider
    ws.default_model = settings.default_model
    ws.default_base_url = settings.default_base_url
    ws.default_api_key = settings.default_api_key
    ws.llm_profiles = list(settings.llm_profiles)
    ws.codex_connections = list(settings.codex_connections)


def _global_settings_from_legacy(payload: dict) -> GlobalSettingsEntity:
    return GlobalSettingsEntity(
        default_provider=LLMProvider(payload.get("default_provider", "anthropic")),
        default_model=payload.get("default_model", "claude-sonnet-4-6"),
        default_base_url=payload.get("default_base_url", ""),
        default_api_key=payload.get("default_api_key", ""),
        llm_profiles=[
            LLMProfileEntity(
                id=item.get("id", ""),
                name=item.get("name", ""),
                provider=LLMProvider(item.get("provider", "anthropic")),
                model=item.get("model", ""),
                base_url=item.get("base_url", ""),
                api_key=item.get("api_key", ""),
            )
            for item in payload.get("llm_profiles", [])
            if isinstance(item, dict) and item.get("name") and item.get("model")
        ],
        codex_connections=[
            CodexConnectionEntity(
                id=item.get("id", ""),
                name=item.get("name", ""),
                provider=LLMProvider(item.get("provider", "openai_codex")),
                auth_mode=item.get("auth_mode", "chatgpt_codex_login"),
                account_label=item.get("account_label", ""),
                status=item.get("status", "disconnected"),
                credential_ref=item.get("credential_ref", ""),
                last_verified_at=item.get("last_verified_at", ""),
                install_status=item.get("install_status", "unknown"),
                install_path=item.get("install_path", ""),
                login_status=item.get("login_status", "unknown"),
                last_checked_at=item.get("last_checked_at", ""),
                last_error=item.get("last_error", ""),
                cli_version=item.get("cli_version", ""),
                os_family=item.get("os_family", ""),
            )
            for item in payload.get("codex_connections", [])
            if isinstance(item, dict) and item.get("name")
        ],
    )


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
