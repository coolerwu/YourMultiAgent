"""
adapter/agent_controller.py

Agent HTTP 接入层：协议转换，不含业务逻辑。
路由前缀 /api/graphs
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional

from server.app.agent.agent_app_service import AgentAppService
from server.app.agent.command.create_agent_cmd import (
    AgentNodeCmd,
    CreateGraphCmd,
    GraphEdgeCmd,
    UpdateGraphCmd,
)
from server.app.agent.command.run_agent_cmd import RunGraphCmd
from server.domain.agent.entity.agent_entity import EdgeCondition, LLMProvider
from server.container import get_agent_service

router = APIRouter(prefix="/api/graphs", tags=["Agent"])


# ── Pydantic 请求/响应模型 ────────────────────────────────────

class AgentNodeReq(BaseModel):
    id: str
    name: str
    provider: LLMProvider
    model: str
    system_prompt: str
    temperature: float = 0.7
    max_tokens: int = 4096
    tools: list[str] = Field(default_factory=list)


class GraphEdgeReq(BaseModel):
    from_node: str
    to_node: str
    condition: EdgeCondition = EdgeCondition.ALWAYS
    condition_expr: Optional[str] = None


class CreateGraphReq(BaseModel):
    name: str
    entry_node: str
    agents: list[AgentNodeReq] = Field(default_factory=list)
    edges: list[GraphEdgeReq] = Field(default_factory=list)


class RunGraphReq(BaseModel):
    user_message: str
    session_id: str = ""


# ── 路由 ─────────────────────────────────────────────────────

@router.get("")
async def list_graphs(svc: AgentAppService = Depends(get_agent_service)):
    return await svc.list_graphs()


@router.get("/{graph_id}")
async def get_graph(graph_id: str, svc: AgentAppService = Depends(get_agent_service)):
    vo = await svc.get_graph(graph_id)
    if not vo:
        raise HTTPException(status_code=404, detail="Graph 不存在")
    return vo


@router.post("")
async def create_graph(req: CreateGraphReq, svc: AgentAppService = Depends(get_agent_service)):
    cmd = CreateGraphCmd(
        name=req.name,
        entry_node=req.entry_node,
        agents=[AgentNodeCmd(**a.model_dump()) for a in req.agents],
        edges=[GraphEdgeCmd(**e.model_dump()) for e in req.edges],
    )
    return await svc.create_graph(cmd)


@router.put("/{graph_id}")
async def update_graph(
    graph_id: str, req: CreateGraphReq, svc: AgentAppService = Depends(get_agent_service)
):
    cmd = UpdateGraphCmd(
        graph_id=graph_id,
        name=req.name,
        entry_node=req.entry_node,
        agents=[AgentNodeCmd(**a.model_dump()) for a in req.agents],
        edges=[GraphEdgeCmd(**e.model_dump()) for e in req.edges],
    )
    return await svc.update_graph(cmd)


@router.delete("/{graph_id}")
async def delete_graph(graph_id: str, svc: AgentAppService = Depends(get_agent_service)):
    ok = await svc.delete_graph(graph_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Graph 不存在")
    return {"success": True}


@router.post("/{graph_id}/run")
async def run_graph(
    graph_id: str, req: RunGraphReq, svc: AgentAppService = Depends(get_agent_service)
):
    """SSE 流式执行"""
    cmd = RunGraphCmd(graph_id=graph_id, user_message=req.user_message, session_id=req.session_id)
    try:
        return StreamingResponse(
            svc.run_graph(cmd),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
