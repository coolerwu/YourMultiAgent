"""
app/agent/workspace_app_service.py

Workspace 应用服务：CRUD 编排。
"""

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from server.app.agent.command.create_agent_cmd import AgentNodeCmd
from server.config import get_data_dir
from server.domain.agent.agent_entity import (
    AgentEntity,
    ChatSessionEntity,
    CodexConnectionEntity,
    GlobalSettingsEntity,
    LLMProfileEntity,
    LLMProvider,
    WorkspaceKind,
    WorkspaceEntity,
)
from server.domain.agent.workspace_gateway import WorkspaceGateway
from server.domain.agent.session_history import create_session
from server.support.app_logging import get_logger, log_event

logger = get_logger(__name__)


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
    kind: WorkspaceKind = WorkspaceKind.WORKSPACE
    dir_name: str = ""
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
    kind: WorkspaceKind = WorkspaceKind.WORKSPACE
    dir_name: str = ""
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
        default_provider, default_model, default_base_url, default_api_key = _workspace_default_llm_config(settings)
        default_profile_id = _default_llm_profile_id(settings)
        ws = WorkspaceEntity(
            id=str(uuid.uuid4()),
            name=cmd.name,
            kind=cmd.kind,
            work_dir=_resolve_workspace_dir(cmd.name, cmd.work_dir, cmd.dir_name),
            dir_name=cmd.dir_name,
            default_provider=default_provider,
            default_model=default_model,
            default_base_url=default_base_url,
            default_api_key=default_api_key,
            llm_profiles=list(settings.llm_profiles),
            codex_connections=list(settings.codex_connections),
            coordinator=_default_workspace_agent(
                cmd.kind,
                default_provider,
                default_model,
                llm_profile_id=default_profile_id,
                base_url=default_base_url,
                api_key=default_api_key,
            ),
            workers=[],
        )
        await self._gateway.save(ws)
        log_event(
            logger,
            event="workspace_created",
            layer="app",
            action="create_workspace",
            status="success",
            workspace_id=ws.id,
            extra={"workspace_name": ws.name, "workspace_kind": ws.kind},
        )
        return ws

    async def update_workspace(self, cmd: UpdateWorkspaceCmd) -> WorkspaceEntity:
        current = await self._gateway.find_by_id(cmd.workspace_id)
        settings = await self._gateway.load_global_settings()
        default_provider, default_model, default_base_url, default_api_key = _workspace_default_llm_config(settings)
        default_profile_id = _default_llm_profile_id(settings)
        ws = WorkspaceEntity(
            id=cmd.workspace_id,
            name=cmd.name,
            kind=current.kind if current else cmd.kind,
            work_dir=_resolve_workspace_dir(cmd.name, cmd.work_dir, current.dir_name if current else cmd.dir_name),
            dir_name=current.dir_name if current else cmd.dir_name,
            default_provider=default_provider,
            default_model=default_model,
            default_base_url=default_base_url,
            default_api_key=default_api_key,
            llm_profiles=list(settings.llm_profiles),
            codex_connections=list(settings.codex_connections),
            coordinator=current.coordinator if current else _default_workspace_agent(
                cmd.kind,
                default_provider,
                default_model,
                llm_profile_id=default_profile_id,
                base_url=default_base_url,
                api_key=default_api_key,
            ),
            workers=current.workers if current and current.kind == WorkspaceKind.WORKSPACE else [],
            sessions=current.sessions if current else [],
        )
        await self._gateway.save(ws)
        log_event(
            logger,
            event="workspace_updated",
            layer="app",
            action="update_workspace",
            status="success",
            workspace_id=ws.id,
            extra={"workspace_name": ws.name},
        )
        return ws

    async def list_workspaces(self) -> list[WorkspaceEntity]:
        return await self._gateway.find_all()

    async def get_workspace(self, ws_id: str) -> WorkspaceEntity | None:
        return await self._gateway.find_by_id(ws_id)

    async def delete_workspace(self, ws_id: str) -> bool:
        deleted = await self._gateway.delete(ws_id)
        log_event(
            logger,
            event="workspace_deleted" if deleted else "workspace_delete_missed",
            layer="app",
            action="delete_workspace",
            status="success" if deleted else "client_error",
            workspace_id=ws_id,
        )
        return deleted

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
        log_event(
            logger,
            event="session_created",
            layer="app",
            action="create_session",
            status="success",
            workspace_id=ws_id,
            session_id=session.id,
        )
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
        log_event(
            logger,
            event="session_saved",
            layer="app",
            action="save_session",
            status="success",
            workspace_id=ws_id,
            session_id=session.id,
        )

    async def delete_session(self, ws_id: str, session_id: str) -> bool:
        workspace = await self._gateway.find_by_id(ws_id)
        if workspace is None:
            raise ValueError(f"Workspace 不存在: {ws_id}")
        filtered = [item for item in workspace.sessions if item.id != session_id]
        if len(filtered) == len(workspace.sessions):
            log_event(
                logger,
                event="session_delete_missed",
                layer="app",
                action="delete_session",
                status="client_error",
                workspace_id=ws_id,
                session_id=session_id,
            )
            return False
        workspace.sessions = filtered
        await self._gateway.save(workspace)
        log_event(
            logger,
            event="session_deleted",
            layer="app",
            action="delete_session",
            status="success",
            workspace_id=ws_id,
            session_id=session_id,
        )
        return True

    async def update_orchestration(self, cmd: UpdateWorkspaceOrchestrationCmd) -> WorkspaceEntity:
        current = await self._gateway.find_by_id(cmd.workspace_id)
        if current is None:
            raise ValueError(f"Workspace 不存在: {cmd.workspace_id}")

        current.coordinator = _to_agent_entity(cmd.coordinator, current)
        current.workers = _normalize_workers([_to_agent_entity(worker, current) for worker in cmd.workers])
        await self._gateway.save(current)
        log_event(
            logger,
            event="workspace_orchestration_updated",
            layer="app",
            action="update_orchestration",
            status="success",
            workspace_id=current.id,
            extra={"worker_count": len(current.workers)},
        )
        return current

    async def get_global_settings(self) -> GlobalSettingsEntity:
        return await self._gateway.load_global_settings()

    async def update_global_settings(self, settings: GlobalSettingsEntity) -> GlobalSettingsEntity:
        saved = await self._gateway.save_global_settings(settings)
        workspaces = await self._gateway.find_all()
        default_provider, default_model, default_base_url, default_api_key = _workspace_default_llm_config(saved)
        for workspace in workspaces:
            workspace.default_provider = default_provider
            workspace.default_model = default_model
            workspace.default_base_url = default_base_url
            workspace.default_api_key = default_api_key
            workspace.llm_profiles = list(saved.llm_profiles)
            workspace.codex_connections = list(saved.codex_connections)
            await self._gateway.save(workspace)
        log_event(
            logger,
            event="global_settings_updated",
            layer="app",
            action="update_global_settings",
            status="success",
            extra={
                "workspace_count": len(workspaces),
                "llm_profile_count": len(saved.llm_profiles),
                "codex_connection_count": len(saved.codex_connections),
            },
        )
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


def _resolve_workspace_dir(name: str, work_dir: str, dir_name: str = "") -> str:
    if work_dir.strip():
        return str(Path(work_dir).expanduser().resolve())

    safe_name = dir_name.strip() or "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in name.strip()).strip("-")
    if not safe_name:
        safe_name = "workspace"
    return str((get_data_dir() / "workspaces" / safe_name).resolve())


def _default_coordinator(
    provider: LLMProvider,
    model: str,
    llm_profile_id: str = "",
    base_url: str = "",
    api_key: str = "",
) -> AgentEntity:
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
        llm_profile_id=llm_profile_id,
        base_url=base_url,
        api_key=api_key,
        work_subdir="coordinator",
    )


def _default_chat_agent(
    provider: LLMProvider,
    model: str,
    llm_profile_id: str = "",
    base_url: str = "",
    api_key: str = "",
) -> AgentEntity:
    return AgentEntity(
        id="chat",
        name="单聊助手",
        provider=provider,
        model=model,
        system_prompt=(
            "你是当前单聊目录中的长期助手。"
            "需要结合该目录下的历史会话摘要、结构化记忆和当前用户消息，连续地完成对话。"
            "如果需要产出文件或中间结果，统一写入当前目录或其子目录，并明确告知路径。"
            "不要虚构已执行的操作；工具不足时直接说明。"
        ),
        tools=[],
        llm_profile_id=llm_profile_id,
        base_url=base_url,
        api_key=api_key,
        work_subdir="",
    )


def _default_workspace_agent(
    kind: WorkspaceKind,
    provider: LLMProvider,
    model: str,
    llm_profile_id: str = "",
    base_url: str = "",
    api_key: str = "",
) -> AgentEntity:
    if kind == WorkspaceKind.CHAT:
        return _default_chat_agent(provider, model, llm_profile_id=llm_profile_id, base_url=base_url, api_key=api_key)
    return _default_coordinator(provider, model, llm_profile_id=llm_profile_id, base_url=base_url, api_key=api_key)


def _to_agent_entity(cmd: AgentNodeCmd, workspace: WorkspaceEntity) -> AgentEntity:
    provider = cmd.provider
    model = str(cmd.model or "").strip()
    llm_profile_id = str(cmd.llm_profile_id or "").strip()
    codex_connection_id = str(cmd.codex_connection_id or "").strip()
    base_url = str(cmd.base_url or "").strip()
    api_key = str(cmd.api_key or "").strip()

    if provider == LLMProvider.OPENAI_CODEX:
        llm_profile_id = ""
        base_url = ""
        api_key = ""
    else:
        codex_connection_id = ""
        profile = _find_llm_profile(workspace, llm_profile_id)
        if profile is not None:
            provider = profile.provider
            model = profile.model
            base_url = profile.base_url
            if not api_key:
                api_key = profile.api_key
        else:
            llm_profile_id = ""
            if not model:
                model = _fallback_model_for_provider(provider, workspace)
            if provider != LLMProvider.OPENAI_COMPAT:
                base_url = ""

    return AgentEntity(
        id=cmd.id,
        name=cmd.name,
        provider=provider,
        model=model,
        system_prompt=cmd.system_prompt,
        temperature=cmd.temperature,
        max_tokens=cmd.max_tokens,
        tools=cmd.tools,
        llm_profile_id=llm_profile_id,
        codex_connection_id=codex_connection_id,
        base_url=base_url,
        api_key=api_key,
        work_subdir=cmd.work_subdir,
        order=cmd.order,
    )


def _fallback_model_for_provider(provider: LLMProvider, workspace: WorkspaceEntity) -> str:
    profile = next((item for item in workspace.llm_profiles if item.provider == provider and item.model), None)
    if profile is not None:
        return profile.model
    workspace_default = (workspace.default_model or "").strip()
    if workspace.default_provider == provider and workspace_default:
        return workspace_default
    if provider == LLMProvider.ANTHROPIC:
        return "claude-sonnet-4-6"
    if provider == LLMProvider.OPENAI:
        return "gpt-4o"
    if provider == LLMProvider.OPENAI_COMPAT:
        return "deepseek-reasoner"
    return workspace_default or "claude-sonnet-4-6"


def _find_llm_profile(workspace: WorkspaceEntity, profile_id: str) -> LLMProfileEntity | None:
    if not profile_id:
        return None
    return next((item for item in workspace.llm_profiles if item.id == profile_id), None)


def _default_llm_profile_id(settings: GlobalSettingsEntity) -> str:
    return settings.llm_profiles[0].id if settings.llm_profiles else ""


def _workspace_default_llm_config(
    settings: GlobalSettingsEntity,
) -> tuple[LLMProvider, str, str, str]:
    if settings.llm_profiles:
        profile = settings.llm_profiles[0]
        return profile.provider, profile.model, profile.base_url, profile.api_key
    return LLMProvider.ANTHROPIC, "claude-sonnet-4-6", "", ""


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
