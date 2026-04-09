"""
infra/worker/local_worker.py

WorkerGateway 的本机实现。
invoke 支持 context 参数，用于注入 work_dir 等运行时信息。
"""

from typing import Any

from server.domain.worker.capability_entity import CapabilityEntity
from server.domain.worker.worker_entity import WorkerInfoEntity
from server.domain.worker.worker_gateway import WorkerGateway
from server.infra.worker import registry
from server.support.app_logging import get_logger, log_event

logger = get_logger(__name__)


class LocalWorker(WorkerGateway):
    """内置 Local Worker，与 Server 同进程运行"""

    def list_capabilities(self) -> list[CapabilityEntity]:
        return registry.get_all_capabilities()

    def list_workers(self) -> list[WorkerInfoEntity]:
        capabilities = self.list_capabilities()
        return [
            WorkerInfoEntity(
                worker_id="local",
                label="Local Worker",
                kind="local",
                status="online",
                registered_capabilities=capabilities,
                enabled_capability_names=[item.name for item in capabilities],
            )
        ]

    def set_enabled_capabilities(self, worker_id: str, capability_names: list[str]) -> WorkerInfoEntity:
        if worker_id != "local":
            raise ValueError(f"Worker 不存在: {worker_id}")
        capabilities = self.list_capabilities()
        return WorkerInfoEntity(
            worker_id="local",
            label="Local Worker",
            kind="local",
            status="online",
            registered_capabilities=capabilities,
            enabled_capability_names=[item.name for item in capabilities],
        )

    async def invoke(
        self,
        capability_name: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Any:
        log_event(
            logger,
            event="local_worker_invoke_started",
            layer="worker",
            action="invoke_local",
            status="started",
            worker_id="local",
            extra={"capability_name": capability_name},
        )
        result = await registry.invoke(capability_name, params, context)
        log_event(
            logger,
            event="local_worker_invoke_finished",
            layer="worker",
            action="invoke_local",
            status="success",
            worker_id="local",
            extra={"capability_name": capability_name},
        )
        return result
