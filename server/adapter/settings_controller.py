"""
adapter/settings_controller.py

全局设置接入层：当前主要负责共享 Provider / LLM 配置。
路由前缀 /api/settings
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from server.app.settings.app_log_service import AppLogService
from server.app.agent.workspace_app_service import WorkspaceAppService
from server.app.settings.codex_runtime_service import CodexRuntimeService
from server.container import get_app_log_service, get_codex_runtime_service, get_workspace_service
from server.domain.agent.entity.agent_entity import CodexConnectionEntity, GlobalSettingsEntity, LLMProfileEntity, LLMProvider

router = APIRouter(prefix="/api/settings", tags=["Settings"])


class LLMProfileReq(BaseModel):
    id: str = ""
    name: str
    provider: LLMProvider
    model: str
    base_url: str = ""
    api_key: str = ""


class CodexConnectionReq(BaseModel):
    id: str = ""
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


class GlobalSettingsReq(BaseModel):
    default_provider: LLMProvider = LLMProvider.ANTHROPIC
    default_model: str = "claude-sonnet-4-6"
    default_base_url: str = ""
    default_api_key: str = ""
    llm_profiles: list[LLMProfileReq] = Field(default_factory=list)
    codex_connections: list[CodexConnectionReq] = Field(default_factory=list)


@router.get("/providers")
async def get_provider_settings(
    svc: WorkspaceAppService = Depends(get_workspace_service),
    codex_runtime: CodexRuntimeService = Depends(get_codex_runtime_service),
):
    settings = await svc.get_global_settings()
    settings.codex_connections = await codex_runtime.enrich_connections(settings.codex_connections)
    return settings


@router.put("/providers")
async def update_provider_settings(
    req: GlobalSettingsReq,
    svc: WorkspaceAppService = Depends(get_workspace_service),
):
    settings = GlobalSettingsEntity(
        default_provider=req.default_provider,
        default_model=req.default_model,
        default_base_url=req.default_base_url,
        default_api_key=req.default_api_key,
        llm_profiles=[
            LLMProfileEntity(
                id=item.id,
                name=item.name,
                provider=item.provider,
                model=item.model,
                base_url=item.base_url,
                api_key=item.api_key,
            )
            for item in req.llm_profiles
        ],
        codex_connections=[
            CodexConnectionEntity(
                id=item.id,
                name=item.name,
                provider=item.provider,
                auth_mode=item.auth_mode,
                account_label=item.account_label,
                status=item.status,
                credential_ref=item.credential_ref,
                last_verified_at=item.last_verified_at,
                install_status=item.install_status,
                install_path=item.install_path,
                login_status=item.login_status,
                last_checked_at=item.last_checked_at,
                last_error=item.last_error,
                cli_version=item.cli_version,
                os_family=item.os_family,
            )
            for item in req.codex_connections
        ],
    )
    return await svc.update_global_settings(settings)


@router.get("/codex-connections")
async def get_codex_connections(
    svc: WorkspaceAppService = Depends(get_workspace_service),
    codex_runtime: CodexRuntimeService = Depends(get_codex_runtime_service),
):
    settings = await svc.get_global_settings()
    return await codex_runtime.enrich_connections(settings.codex_connections)


@router.put("/codex-connections")
async def update_codex_connections(
    req: list[CodexConnectionReq],
    svc: WorkspaceAppService = Depends(get_workspace_service),
):
    settings = await svc.get_global_settings()
    settings.codex_connections = [
        CodexConnectionEntity(
            id=item.id,
            name=item.name,
            provider=item.provider,
            auth_mode=item.auth_mode,
            account_label=item.account_label,
            status=item.status,
            credential_ref=item.credential_ref,
            last_verified_at=item.last_verified_at,
            install_status=item.install_status,
            install_path=item.install_path,
            login_status=item.login_status,
            last_checked_at=item.last_checked_at,
            last_error=item.last_error,
            cli_version=item.cli_version,
            os_family=item.os_family,
        )
        for item in req
    ]
    saved = await svc.update_global_settings(settings)
    return saved.codex_connections


@router.get("/codex/runtime")
async def get_codex_runtime_summary(
    svc: CodexRuntimeService = Depends(get_codex_runtime_service),
):
    return await svc.runtime_summary()


@router.get("/logs/app")
async def get_app_log(
    lines: int = 300,
    svc: AppLogService = Depends(get_app_log_service),
):
    return svc.get_app_log(lines)


@router.post("/codex-connections/{connection_id}/check")
async def check_codex_connection(
    connection_id: str,
    svc: CodexRuntimeService = Depends(get_codex_runtime_service),
):
    try:
        result = await svc.refresh_connection(connection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "connection": result.connection,
        "message": result.message,
        "manual_command": result.manual_command,
        "details": result.details,
    }


@router.post("/codex-connections/{connection_id}/install")
async def install_codex_connection(
    connection_id: str,
    svc: CodexRuntimeService = Depends(get_codex_runtime_service),
):
    try:
        result = await svc.install_connection(connection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "connection": result.connection,
        "message": result.message,
        "manual_command": result.manual_command,
        "details": result.details,
    }


@router.post("/codex-connections/{connection_id}/login")
async def login_codex_connection(
    connection_id: str,
    svc: CodexRuntimeService = Depends(get_codex_runtime_service),
):
    try:
        result = await svc.login_connection(connection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "connection": result.connection,
        "message": result.message,
        "manual_command": result.manual_command,
        "details": result.details,
    }
