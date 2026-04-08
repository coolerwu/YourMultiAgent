"""
app/agent/workspace_app_service.py

Workspace 应用服务：CRUD 编排。
"""

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from server.app.agent.command.create_agent_cmd import AgentNodeCmd
from server.config import get_data_dir
from server.domain.agent.entity.agent_entity import (
    AgentEntity,
    ChatSessionEntity,
    CodexConnectionEntity,
    GlobalSettingsEntity,
    LLMProfileEntity,
    LLMProvider,
    WorkspaceEntity,
)
from server.domain.agent.gateway.workspace_gateway import WorkspaceGateway
from server.domain.agent.service.session_history import create_session


@dataclass
class LLMProfileCmd:
    id: str
    name: str
    provider: LLMProvider
    model: str
    base_url: str = ""
    api_key: str = ""


@dataclass
class CodexConnectionCmd:
    id: str
    name: str
    provider: LLMProvider = LLMProvider.OPENAI_CODEX
    auth_mode: str = "chatgpt_codex_login"
    account_label: str = ""
    status: str = "disconnected"
    credential_ref: str = ""
    last_verified_at: str = ""
    install_status: str = "unknown"
    install_path: str = ""
    login_status: str = "unknown"
    last_checked_at: str = ""
    last_error: str = ""
    cli_version: str = ""
    os_family: str = ""


@dataclass
class CreateWorkspaceCmd:
    name: str
    work_dir: str
    default_provider: LLMProvider
    default_model: str
    default_base_url: str = ""
    default_api_key: str = ""
    llm_profiles: list[LLMProfileCmd] = field(default_factory=list)
    codex_connections: list[CodexConnectionCmd] = field(default_factory=list)


@dataclass
class UpdateWorkspaceCmd:
    workspace_id: str
    name: str
    work_dir: str
    default_provider: LLMProvider
    default_model: str
    default_base_url: str = ""
    default_api_key: str = ""
    llm_profiles: list[LLMProfileCmd] = field(default_factory=list)
    codex_connections: list[CodexConnectionCmd] = field(default_factory=list)


@dataclass
class UpdateWorkspaceOrchestrationCmd:
    workspace_id: str
    coordinator: AgentNodeCmd
    workers: list[AgentNodeCmd] = field(default_factory=list)


class WorkspaceAppService:
    def __init__(self, gateway: WorkspaceGateway) -> None:
        self._gateway = gateway

    async def create_workspace(self, cmd: CreateWorkspaceCmd) -> WorkspaceEntity:
        settings = await self._gateway.load_global_settings()
        effective = _effective_global_settings(settings, cmd)
        ws = WorkspaceEntity(
            id=str(uuid.uuid4()),
            name=cmd.name,
            work_dir=_resolve_workspace_dir(cmd.name, cmd.work_dir),
            dir_name="",
            default_provider=effective.default_provider,
            default_model=effective.default_model,
            default_base_url=effective.default_base_url,
            default_api_key=effective.default_api_key,
            llm_profiles=list(effective.llm_profiles),
            codex_connections=list(effective.codex_connections),
            coordinator=_default_coordinator(effective.default_provider, effective.default_model),
            workers=[],
        )
        await self._gateway.save(ws)
        return ws

    async def update_workspace(self, cmd: UpdateWorkspaceCmd) -> WorkspaceEntity:
        current = await self._gateway.find_by_id(cmd.workspace_id)
        settings = await self._gateway.load_global_settings()
        ws = WorkspaceEntity(
            id=cmd.workspace_id,
            name=cmd.name,
            work_dir=_resolve_workspace_dir(cmd.name, cmd.work_dir),
            dir_name="",
            default_provider=settings.default_provider,
            default_model=settings.default_model,
            default_base_url=settings.default_base_url,
            default_api_key=settings.default_api_key,
            llm_profiles=list(settings.llm_profiles),
            codex_connections=list(settings.codex_connections),
            coordinator=current.coordinator if current else _default_coordinator(settings.default_provider, settings.default_model),
            workers=current.workers if current else [],
            sessions=current.sessions if current else [],
        )
        await self._gateway.save(ws)
        return ws

    async def list_workspaces(self) -> list[WorkspaceEntity]:
        return await self._gateway.find_all()

    async def get_workspace(self, ws_id: str) -> WorkspaceEntity | None:
        return await self._gateway.find_by_id(ws_id)

    async def delete_workspace(self, ws_id: str) -> bool:
        return await self._gateway.delete(ws_id)

    async def get_orchestration(self, ws_id: str) -> WorkspaceEntity | None:
        return await self._gateway.find_by_id(ws_id)

    async def list_sessions(self, ws_id: str) -> list[ChatSessionEntity]:
        workspace = await self._gateway.find_by_id(ws_id)
        if workspace is None:
            raise ValueError(f"Workspace 不存在: {ws_id}")
        sessions = sorted(workspace.sessions, key=lambda item: item.updated_at, reverse=True)
        return sessions

    async def create_session(self, ws_id: str, title_hint: str = "") -> ChatSessionEntity:
        workspace = await self._gateway.find_by_id(ws_id)
        if workspace is None:
            raise ValueError(f"Workspace 不存在: {ws_id}")
        session = create_session(title_hint)
        workspace.sessions.insert(0, session)
        await self._gateway.save(workspace)
        return session

    async def get_session(self, ws_id: str, session_id: str) -> ChatSessionEntity | None:
        workspace = await self._gateway.find_by_id(ws_id)
        if workspace is None:
            return None
        return next((item for item in workspace.sessions if item.id == session_id), None)

    async def save_session(self, ws_id: str, session: ChatSessionEntity) -> None:
        workspace = await self._gateway.find_by_id(ws_id)
        if workspace is None:
            raise ValueError(f"Workspace 不存在: {ws_id}")

        for index, existing in enumerate(workspace.sessions):
            if existing.id == session.id:
                workspace.sessions[index] = session
                break
        else:
            workspace.sessions.insert(0, session)

        workspace.sessions.sort(key=lambda item: item.updated_at, reverse=True)
        await self._gateway.save(workspace)

    async def delete_session(self, ws_id: str, session_id: str) -> bool:
        workspace = await self._gateway.find_by_id(ws_id)
        if workspace is None:
            raise ValueError(f"Workspace 不存在: {ws_id}")
        filtered = [item for item in workspace.sessions if item.id != session_id]
        if len(filtered) == len(workspace.sessions):
            return False
        workspace.sessions = filtered
        await self._gateway.save(workspace)
        return True

    async def update_orchestration(self, cmd: UpdateWorkspaceOrchestrationCmd) -> WorkspaceEntity:
        current = await self._gateway.find_by_id(cmd.workspace_id)
        if current is None:
            raise ValueError(f"Workspace 不存在: {cmd.workspace_id}")

        current.coordinator = _to_agent_entity(cmd.coordinator)
        current.workers = _normalize_workers([_to_agent_entity(worker) for worker in cmd.workers])
        await self._gateway.save(current)
        return current

    async def get_global_settings(self) -> GlobalSettingsEntity:
        return await self._gateway.load_global_settings()

    async def update_global_settings(self, settings: GlobalSettingsEntity) -> GlobalSettingsEntity:
        saved = await self._gateway.save_global_settings(settings)
        workspaces = await self._gateway.find_all()
        for workspace in workspaces:
            workspace.default_provider = saved.default_provider
            workspace.default_model = saved.default_model
            workspace.default_base_url = saved.default_base_url
            workspace.default_api_key = saved.default_api_key
            workspace.llm_profiles = list(saved.llm_profiles)
            workspace.codex_connections = list(saved.codex_connections)
            await self._gateway.save(workspace)
        return saved


def _to_profile_entity(cmd: LLMProfileCmd) -> LLMProfileEntity:
    return LLMProfileEntity(
        id=cmd.id or str(uuid.uuid4()),
        name=cmd.name,
        provider=cmd.provider,
        model=cmd.model,
        base_url=cmd.base_url,
        api_key=cmd.api_key,
    )


def _to_codex_connection_entity(cmd: CodexConnectionCmd) -> CodexConnectionEntity:
    return CodexConnectionEntity(
        id=cmd.id or str(uuid.uuid4()),
        name=cmd.name,
        provider=cmd.provider,
        auth_mode=cmd.auth_mode,
        account_label=cmd.account_label,
        status=cmd.status,
        credential_ref=cmd.credential_ref,
        last_verified_at=cmd.last_verified_at,
        install_status=cmd.install_status,
        install_path=cmd.install_path,
        login_status=cmd.login_status,
        last_checked_at=cmd.last_checked_at,
        last_error=cmd.last_error,
        cli_version=cmd.cli_version,
        os_family=cmd.os_family,
    )


def _effective_global_settings(current: GlobalSettingsEntity, cmd: CreateWorkspaceCmd) -> GlobalSettingsEntity:
    use_cmd_defaults = (
        not current.llm_profiles
        and current.default_provider == LLMProvider.ANTHROPIC
        and current.default_model == "claude-sonnet-4-6"
        and not current.default_base_url
        and not current.default_api_key
    )
    return GlobalSettingsEntity(
        default_provider=cmd.default_provider if use_cmd_defaults else current.default_provider,
        default_model=cmd.default_model if use_cmd_defaults else current.default_model,
        default_base_url=cmd.default_base_url if use_cmd_defaults else current.default_base_url,
        default_api_key=cmd.default_api_key if use_cmd_defaults else current.default_api_key,
        llm_profiles=[_to_profile_entity(p) for p in cmd.llm_profiles] if use_cmd_defaults else list(current.llm_profiles),
        codex_connections=[_to_codex_connection_entity(item) for item in cmd.codex_connections] if use_cmd_defaults else list(current.codex_connections),
    )


def _resolve_workspace_dir(name: str, work_dir: str) -> str:
    if work_dir.strip():
        return str(Path(work_dir).expanduser().resolve())

    safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in name.strip()).strip("-")
    if not safe_name:
        safe_name = "workspace"
    return str((get_data_dir() / "workspaces" / safe_name).resolve())


def _default_coordinator(provider: LLMProvider, model: str) -> AgentEntity:
    return AgentEntity(
        id="coordinator",
        name="主控智能体",
        provider=provider,
        model=model,
        system_prompt=(
            "你是当前 Workspace 的主控智能体，负责统筹整个任务执行流程。"
            "先理解用户目标，再判断需要哪些 Worker 参与。"
            "将任务拆成清晰、可执行的子任务，并为每个 Worker 指定目标、输入、输出和完成标准。"
            "共享交接物统一写入当前 Workspace 的 `shared/` 目录，例如 `workspace/<workspace_name>/shared/`，"
            "不要把 Worker 私有过程文件当成默认交接物。"
            "避免角色越权，例如产品类 Worker 不直接产出研发最终实现。"
            "在所有 Worker 完成后，汇总关键结果、交付物路径和最终结论。"
        ),
        tools=[],
        work_subdir="coordinator",
    )


def _to_agent_entity(cmd: AgentNodeCmd) -> AgentEntity:
    return AgentEntity(
        id=cmd.id,
        name=cmd.name,
        provider=cmd.provider,
        model=cmd.model,
        system_prompt=cmd.system_prompt,
        temperature=cmd.temperature,
        max_tokens=cmd.max_tokens,
        tools=cmd.tools,
        llm_profile_id=cmd.llm_profile_id,
        codex_connection_id=cmd.codex_connection_id,
        base_url=cmd.base_url,
        api_key=cmd.api_key,
        work_subdir=cmd.work_subdir,
        order=cmd.order,
    )


def _normalize_workers(workers: list[AgentEntity]) -> list[AgentEntity]:
    ordered = sorted(
        enumerate(workers),
        key=lambda item: (
            item[1].order if item[1].order > 0 else item[0] + 1,
            item[0],
        ),
    )
    return [
        AgentEntity(
            id=worker.id,
            name=worker.name,
            provider=worker.provider,
            model=worker.model,
            system_prompt=worker.system_prompt,
            temperature=worker.temperature,
            max_tokens=worker.max_tokens,
            tools=list(worker.tools),
            llm_profile_id=worker.llm_profile_id,
            codex_connection_id=worker.codex_connection_id,
            base_url=worker.base_url,
            api_key=worker.api_key,
            work_subdir=worker.work_subdir,
            order=index,
        )
        for index, (_, worker) in enumerate(ordered, start=1)
    ]
