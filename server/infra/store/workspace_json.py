"""
infra/store/workspace_json.py

setting.json 与 workspace.json 的共享读写辅助。
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from server.domain.agent.entity.agent_entity import (
    AgentEntity,
    ChatMessageEntity,
    ChatSessionEntity,
    CodexConnectionEntity,
    EdgeCondition,
    GlobalSettingsEntity,
    GraphEdge,
    GraphEntity,
    LLMProfileEntity,
    LLMProvider,
    MemoryItemEntity,
    WorkspaceEntity,
)


def sanitize_workspace_name(name: str) -> str:
    safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in name.strip()).strip("-")
    return safe_name or "workspace"


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def setting_path(data_dir: Path) -> Path:
    return data_dir / "setting.json"


def workspace_root_dir(data_dir: Path) -> Path:
    return data_dir / "workspaces"


def workspace_file_path(data_dir: Path, dir_name: str) -> Path:
    return workspace_root_dir(data_dir) / dir_name / "workspace.json"


def load_setting_entries(data_dir: Path) -> list[dict]:
    raw = read_json(setting_path(data_dir), {"version": 2, "workspaces": []})
    if isinstance(raw, dict) and isinstance(raw.get("workspaces"), list):
        return raw["workspaces"]
    return []


def save_setting_entries(data_dir: Path, entries: list[dict]) -> None:
    raw = read_json(setting_path(data_dir), {"version": 2, "workspaces": []})
    if not isinstance(raw, dict):
        raw = {"version": 2}
    raw["version"] = 2
    raw["workspaces"] = entries
    write_json(setting_path(data_dir), raw)


def load_global_settings(data_dir: Path) -> GlobalSettingsEntity:
    raw = read_json(setting_path(data_dir), {"version": 2, "workspaces": []})
    settings = raw.get("global_settings", {}) if isinstance(raw, dict) else {}
    if not isinstance(settings, dict):
        settings = {}
    return GlobalSettingsEntity(
        default_provider=LLMProvider(settings.get("default_provider", "anthropic")),
        default_model=settings.get("default_model", "claude-sonnet-4-6"),
        default_base_url=settings.get("default_base_url", ""),
        default_api_key=settings.get("default_api_key", ""),
        llm_profiles=[
            LLMProfileEntity(
                id=p["id"],
                name=p["name"],
                provider=LLMProvider(p["provider"]),
                model=p["model"],
                base_url=p.get("base_url", ""),
                api_key=p.get("api_key", ""),
            )
            for p in settings.get("llm_profiles", [])
            if isinstance(p, dict) and "id" in p and "name" in p and "provider" in p and "model" in p
        ],
        codex_connections=[
            CodexConnectionEntity(
                id=item["id"],
                name=item["name"],
                provider=LLMProvider(item.get("provider", "openai_codex")),
                auth_mode=item.get("auth_mode", "chatgpt_codex_login"),
                account_label=item.get("account_label", ""),
                status=item.get("status", "disconnected"),
                credential_ref=item.get("credential_ref", ""),
                last_verified_at=item.get("last_verified_at", ""),
            )
            for item in settings.get("codex_connections", [])
            if isinstance(item, dict) and "id" in item and "name" in item
        ],
    )


def save_global_settings(data_dir: Path, settings: GlobalSettingsEntity) -> None:
    raw = read_json(setting_path(data_dir), {"version": 2, "workspaces": []})
    if not isinstance(raw, dict):
        raw = {"version": 2, "workspaces": []}
    raw["version"] = 2
    raw["global_settings"] = {
        "default_provider": settings.default_provider,
        "default_model": settings.default_model,
        "default_base_url": settings.default_base_url,
        "default_api_key": settings.default_api_key,
        "llm_profiles": [dataclasses.asdict(profile) for profile in settings.llm_profiles],
        "codex_connections": [dataclasses.asdict(item) for item in settings.codex_connections],
    }
    write_json(setting_path(data_dir), raw)


def load_workspace_payload(path: Path) -> dict:
    return read_json(path, {})


def save_workspace_payload(path: Path, payload: dict) -> None:
    write_json(path, payload)


def workspace_to_payload(ws: WorkspaceEntity, graphs: list[GraphEntity]) -> dict:
    return {
        "id": ws.id,
        "name": ws.name,
        "work_dir": ws.work_dir,
        "dir_name": ws.dir_name,
        "coordinator": dataclasses.asdict(ws.coordinator) if ws.coordinator else None,
        "workers": [dataclasses.asdict(worker) for worker in ws.workers],
        "sessions": [dataclasses.asdict(session) for session in ws.sessions],
        "graphs": [dataclasses.asdict(graph) for graph in graphs],
    }


def workspace_from_payload(d: dict) -> WorkspaceEntity:
    return WorkspaceEntity(
        id=d["id"],
        name=d["name"],
        work_dir=d["work_dir"],
        dir_name=d.get("dir_name", ""),
        default_provider=LLMProvider(d.get("default_provider", "anthropic")),
        default_model=d.get("default_model", "claude-sonnet-4-6"),
        default_base_url=d.get("default_base_url", ""),
        default_api_key=d.get("default_api_key", ""),
        llm_profiles=[
            LLMProfileEntity(
                id=p["id"],
                name=p["name"],
                provider=LLMProvider(p["provider"]),
                model=p["model"],
                base_url=p.get("base_url", ""),
                api_key=p.get("api_key", ""),
            )
            for p in d.get("llm_profiles", [])
        ],
        codex_connections=[
            CodexConnectionEntity(
                id=item["id"],
                name=item["name"],
                provider=LLMProvider(item.get("provider", "openai_codex")),
                auth_mode=item.get("auth_mode", "chatgpt_codex_login"),
                account_label=item.get("account_label", ""),
                status=item.get("status", "disconnected"),
                credential_ref=item.get("credential_ref", ""),
                last_verified_at=item.get("last_verified_at", ""),
            )
            for item in d.get("codex_connections", [])
            if isinstance(item, dict) and "id" in item and "name" in item
        ],
        coordinator=_agent_from_dict(d["coordinator"]) if d.get("coordinator") else None,
        workers=[_agent_from_dict(worker) for worker in d.get("workers", [])],
        sessions=[_session_from_dict(session) for session in d.get("sessions", [])],
    )


def graphs_from_payload(d: dict) -> list[GraphEntity]:
    return [_graph_from_dict(item) for item in d.get("graphs", [])]


def _graph_from_dict(d: dict) -> GraphEntity:
    return GraphEntity(
        id=d["id"],
        name=d["name"],
        entry_node=d["entry_node"],
        workspace_id=d.get("workspace_id", ""),
        agents=[_agent_from_dict(a) for a in d.get("agents", [])],
        edges=[
            GraphEdge(
                from_node=e["from_node"],
                to_node=e["to_node"],
                condition=EdgeCondition(e.get("condition", "always")),
                condition_expr=e.get("condition_expr"),
                artifact=e.get("artifact", ""),
                prompt=e.get("prompt", ""),
            )
            for e in d.get("edges", [])
        ],
    )


def _agent_from_dict(d: dict) -> AgentEntity:
    return AgentEntity(
        id=d["id"],
        name=d["name"],
        provider=LLMProvider(d["provider"]),
        model=d["model"],
        system_prompt=d["system_prompt"],
        temperature=d.get("temperature", 0.7),
        max_tokens=d.get("max_tokens", 4096),
        tools=d.get("tools", []),
        llm_profile_id=d.get("llm_profile_id", ""),
        codex_connection_id=d.get("codex_connection_id", ""),
        base_url=d.get("base_url", ""),
        api_key=d.get("api_key", ""),
        work_subdir=d.get("work_subdir", ""),
        order=d.get("order", 0),
    )


def _session_from_dict(d: dict) -> ChatSessionEntity:
    return ChatSessionEntity(
        id=d["id"],
        title=d.get("title", "新会话"),
        created_at=d.get("created_at", ""),
        updated_at=d.get("updated_at", ""),
        status=d.get("status", "idle"),
        message_count=d.get("message_count", len(d.get("messages", []))),
        summary=d.get("summary", ""),
        memory_items=[
            MemoryItemEntity(
                id=item["id"],
                category=item.get("category", "decision"),
                content=item.get("content", ""),
                confidence=item.get("confidence", 0.5),
                source_message_ids=item.get("source_message_ids", []),
                updated_at=item.get("updated_at", ""),
            )
            for item in d.get("memory_items", [])
        ],
        messages=[
            ChatMessageEntity(
                id=item["id"],
                role=item.get("role", "assistant"),
                kind=item.get("kind", "assistant"),
                content=item.get("content", ""),
                created_at=item.get("created_at", ""),
                actor_id=item.get("actor_id", ""),
                actor_name=item.get("actor_name", ""),
                node=item.get("node", ""),
                session_round=item.get("session_round", 0),
            )
            for item in d.get("messages", [])
        ],
    )
