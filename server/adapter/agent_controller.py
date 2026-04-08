"""
adapter/agent_controller.py

Agent HTTP 接入层：当前只负责 Prompt 优化接口。
路由前缀 /api/agents
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from server.app.agent.agent_app_service import AgentAppService
from server.app.agent.command.generate_worker_cmd import GenerateWorkerCmd
from server.app.agent.command.optimize_prompt_cmd import OptimizePromptCmd
from server.domain.agent.entity.agent_entity import LLMProvider
from server.container import get_agent_service

router = APIRouter(prefix="/api/agents", tags=["Agent"])


class OptimizePromptReq(BaseModel):
    name: str
    system_prompt: str = ""
    prompt_kind: str = "system_prompt"
    goal: str = ""
    workspace_id: str = ""
    source_name: str = ""
    target_name: str = ""
    artifact: str = ""
    provider: LLMProvider = LLMProvider.ANTHROPIC
    model: str = "claude-sonnet-4-6"
    temperature: float = 0.2
    max_tokens: int = 4096
    tools: list[str] = Field(default_factory=list)
    llm_profile_id: str = ""
    codex_connection_id: str = ""
    base_url: str = ""
    api_key: str = ""


class GenerateWorkerReq(BaseModel):
    workspace_id: str = ""
    user_goal: str = ""
    coordinator_name: str = ""
    coordinator_prompt: str = ""
    existing_worker_names: list[str] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)
    provider: LLMProvider = LLMProvider.ANTHROPIC
    model: str = "claude-sonnet-4-6"
    llm_profile_id: str = ""
    codex_connection_id: str = ""
    base_url: str = ""
    api_key: str = ""


@router.post("/prompt-optimize")
async def optimize_prompt(
    req: OptimizePromptReq,
    svc: AgentAppService = Depends(get_agent_service),
):
    cmd = OptimizePromptCmd(**req.model_dump())
    return await svc.optimize_prompt(cmd)


@router.post("/worker-generate")
async def generate_worker(
    req: GenerateWorkerReq,
    svc: AgentAppService = Depends(get_agent_service),
):
    cmd = GenerateWorkerCmd(**req.model_dump())
    return await svc.generate_worker(cmd)
