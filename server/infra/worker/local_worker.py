"""
infra/worker/local_worker.py

WorkerGateway 的本机实现。
invoke 支持 context 参数，用于注入 work_dir 等运行时信息。
"""

from typing import Any

from server.domain.worker.entity.capability_entity import CapabilityEntity
from server.domain.worker.gateway.worker_gateway import WorkerGateway
from server.infra.worker import registry


class LocalWorker(WorkerGateway):
    """内置 Local Worker，与 Server 同进程运行"""

    def list_capabilities(self) -> list[CapabilityEntity]:
        return registry.get_all_capabilities()

    async def invoke(
        self,
        capability_name: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Any:
        return await registry.invoke(capability_name, params, context)
