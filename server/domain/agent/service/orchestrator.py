"""
domain/agent/service/orchestrator.py

AgentOrchestrator：WorkspaceExecutor 的薄包装，负责 work_dir 注入。
yield 事件以 Workspace 单编排运行语义为主。
"""

from typing import AsyncGenerator, Optional

from server.domain.agent.entity.agent_entity import ChatSessionEntity, WorkspaceEntity
from server.domain.agent.gateway.llm_gateway import LLMGateway
from server.domain.agent.service.workspace_executor import WorkspaceExecutor
from server.domain.worker.gateway.worker_gateway import WorkerGateway


class AgentOrchestrator:
    def __init__(
        self,
        worker: WorkerGateway,
        llm_factory: LLMGateway,
        base_work_dir: str = "",
    ) -> None:
        self._worker        = worker
        self._llm_factory   = llm_factory
        self._base_work_dir = base_work_dir

    async def run(
        self,
        workspace: WorkspaceEntity,
        user_message: str,
        session: ChatSessionEntity,
    ) -> AsyncGenerator[dict, None]:
        executor = WorkspaceExecutor(
            workspace=workspace,
            worker_gateway=self._worker,
            llm_factory=self._llm_factory,
            base_work_dir=self._base_work_dir,
        )
        async for event in executor.run(user_message, session):
            yield event
