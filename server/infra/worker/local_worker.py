"""
infra/worker/local_worker.py

WorkerGateway 的本机实现。
调用本进程内已注册的 @capability 函数，无网络开销。
"""

from typing import Any

from server.domain.worker.entity.capability_entity import CapabilityEntity
from server.domain.worker.gateway.worker_gateway import WorkerGateway
from server.infra.worker import registry


class LocalWorker(WorkerGateway):
    """内置 Local Worker，与 Server 同进程运行"""

    def list_capabilities(self) -> list[CapabilityEntity]:
        return registry.get_all_capabilities()

    async def invoke(self, capability_name: str, params: dict[str, Any]) -> Any:
        return await registry.invoke(capability_name, params)
