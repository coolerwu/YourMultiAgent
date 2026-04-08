"""
app/agent/orchestrator.py

AgentOrchestrator：WorkspaceExecutor 的薄包装。
位于 app 层，负责组装依赖并暴露 Workspace 级运行入口。
"""

from typing import AsyncGenerator, Optional

from server.domain.agent.agent_entity import ChatSessionEntity, WorkspaceEntity
from server.domain.agent.llm_gateway import LLMGateway
from server.app.agent.workspace_executor import WorkspaceExecutor
from server.domain.worker.worker_gateway import WorkerGateway


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
