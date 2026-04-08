"""
adapter/settings_controller.py

全局设置接入层：当前主要负责共享 Provider / LLM 配置。
路由前缀 /api/settings
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from server.app.agent.workspace_app_service import WorkspaceAppService
from server.container import get_workspace_service
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


class GlobalSettingsReq(BaseModel):
    default_provider: LLMProvider = LLMProvider.ANTHROPIC
    default_model: str = "claude-sonnet-4-6"
    default_base_url: str = ""
    default_api_key: str = ""
    llm_profiles: list[LLMProfileReq] = Field(default_factory=list)
    codex_connections: list[CodexConnectionReq] = Field(default_factory=list)


@router.get("/providers")
async def get_provider_settings(svc: WorkspaceAppService = Depends(get_workspace_service)):
    return await svc.get_global_settings()


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
            )
            for item in req.codex_connections
        ],
    )
    return await svc.update_global_settings(settings)


@router.get("/codex-connections")
async def get_codex_connections(svc: WorkspaceAppService = Depends(get_workspace_service)):
    settings = await svc.get_global_settings()
    return settings.codex_connections


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
        )
        for item in req
    ]
    saved = await svc.update_global_settings(settings)
    return saved.codex_connections
