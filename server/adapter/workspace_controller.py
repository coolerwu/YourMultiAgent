"""
adapter/workspace_controller.py

Workspace HTTP 接入层：协议转换，不含业务逻辑。
路由前缀 /api/workspaces

REST 端点：
  GET    /api/workspaces          列出所有 Workspace
  POST   /api/workspaces          创建 Workspace
  GET    /api/workspaces/{id}     获取单个 Workspace
  PUT    /api/workspaces/{id}     更新 Workspace（全量）
  DELETE /api/workspaces/{id}     删除 Workspace
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from server.app.agent.workspace_app_service import (
    CreateWorkspaceCmd,
    LLMProfileCmd,
    UpdateWorkspaceCmd,
    UpdateWorkspaceOrchestrationCmd,
    WorkspaceAppService,
)
from server.app.agent.command.create_agent_cmd import AgentNodeCmd
from server.domain.agent.entity.agent_entity import LLMProvider
from server.container import get_workspace_service

class LLMProfileReq(BaseModel):
    id: str = ""
    name: str
    provider: LLMProvider
    model: str
    base_url: str = ""
    api_key: str = ""


router = APIRouter(prefix="/api/workspaces", tags=["Workspace"])


# ── Pydantic 请求模型 ─────────────────────────────────────────

class WorkspaceReq(BaseModel):
    name: str
    work_dir: str = ""
    default_provider: LLMProvider = LLMProvider.ANTHROPIC
    default_model: str = "claude-sonnet-4-6"
    default_base_url: str = ""
    default_api_key: str = ""
    llm_profiles: list[LLMProfileReq] = Field(default_factory=list)


class AgentNodeReq(BaseModel):
    id: str
    name: str
    provider: LLMProvider
    model: str
    system_prompt: str
    temperature: float = 0.7
    max_tokens: int = 4096
    tools: list[str] = Field(default_factory=list)
    llm_profile_id: str = ""
    base_url: str = ""
    api_key: str = ""
    work_subdir: str = ""
    order: int = 0


class OrchestrationReq(BaseModel):
    coordinator: AgentNodeReq
    workers: list[AgentNodeReq] = Field(default_factory=list)


class CreateSessionReq(BaseModel):
    title_hint: str = ""


# ── 路由 ─────────────────────────────────────────────────────

@router.get("")
async def list_workspaces(svc: WorkspaceAppService = Depends(get_workspace_service)):
    return await svc.list_workspaces()


@router.post("")
async def create_workspace(req: WorkspaceReq, svc: WorkspaceAppService = Depends(get_workspace_service)):
    cmd = CreateWorkspaceCmd(
        name=req.name,
        work_dir=req.work_dir,
        default_provider=req.default_provider,
        default_model=req.default_model,
        default_base_url=req.default_base_url,
        default_api_key=req.default_api_key,
        llm_profiles=[LLMProfileCmd(**p.model_dump()) for p in req.llm_profiles],
    )
    return await svc.create_workspace(cmd)


@router.get("/{workspace_id}")
async def get_workspace(workspace_id: str, svc: WorkspaceAppService = Depends(get_workspace_service)):
    ws = await svc.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace 不存在")
    return ws


@router.get("/{workspace_id}/orchestration")
async def get_orchestration(workspace_id: str, svc: WorkspaceAppService = Depends(get_workspace_service)):
    ws = await svc.get_orchestration(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace 不存在")
    return {
        "coordinator": ws.coordinator,
        "workers": ws.workers,
    }


@router.get("/{workspace_id}/sessions")
async def list_sessions(workspace_id: str, svc: WorkspaceAppService = Depends(get_workspace_service)):
    try:
        sessions = await svc.list_sessions(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return sessions


@router.post("/{workspace_id}/sessions")
async def create_session(
    workspace_id: str,
    req: CreateSessionReq,
    svc: WorkspaceAppService = Depends(get_workspace_service),
):
    try:
        return await svc.create_session(workspace_id, req.title_hint)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{workspace_id}/sessions/{session_id}")
async def get_session(
    workspace_id: str,
    session_id: str,
    svc: WorkspaceAppService = Depends(get_workspace_service),
):
    session = await svc.get_session(workspace_id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session 不存在")
    return session


@router.put("/{workspace_id}")
async def update_workspace(
    workspace_id: str, req: WorkspaceReq, svc: WorkspaceAppService = Depends(get_workspace_service)
):
    cmd = UpdateWorkspaceCmd(
        workspace_id=workspace_id,
        name=req.name,
        work_dir=req.work_dir,
        default_provider=req.default_provider,
        default_model=req.default_model,
        default_base_url=req.default_base_url,
        default_api_key=req.default_api_key,
        llm_profiles=[LLMProfileCmd(**p.model_dump()) for p in req.llm_profiles],
    )
    return await svc.update_workspace(cmd)


@router.put("/{workspace_id}/orchestration")
async def update_orchestration(
    workspace_id: str,
    req: OrchestrationReq,
    svc: WorkspaceAppService = Depends(get_workspace_service),
):
    try:
        ws = await svc.update_orchestration(
            UpdateWorkspaceOrchestrationCmd(
                workspace_id=workspace_id,
                coordinator=AgentNodeCmd(**req.coordinator.model_dump()),
                workers=[AgentNodeCmd(**worker.model_dump()) for worker in req.workers],
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "coordinator": ws.coordinator,
        "workers": ws.workers,
    }


@router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: str, svc: WorkspaceAppService = Depends(get_workspace_service)):
    ok = await svc.delete_workspace(workspace_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Workspace 不存在")
    return {"success": True}


@router.delete("/{workspace_id}/sessions/{session_id}")
async def delete_session(
    workspace_id: str,
    session_id: str,
    svc: WorkspaceAppService = Depends(get_workspace_service),
):
    try:
        ok = await svc.delete_session(workspace_id, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Session 不存在")
    return {"success": True}
