"""
app/worker/worker_app_service.py

Worker 应用服务：查询已注册的 capability 列表。
"""

from server.domain.worker.entity.capability_entity import CapabilityEntity
from server.domain.worker.gateway.worker_gateway import WorkerGateway
from server.domain.worker.entity.worker_entity import WorkerInfoEntity


class WorkerAppService:
    def __init__(self, worker: WorkerGateway) -> None:
        self._worker = worker

    def list_capabilities(self) -> list[CapabilityEntity]:
        return self._worker.list_capabilities()

    def list_workers(self) -> list[WorkerInfoEntity]:
        return self._worker.list_workers()

    def set_enabled_capabilities(self, worker_id: str, capability_names: list[str]) -> WorkerInfoEntity:
        return self._worker.set_enabled_capabilities(worker_id, capability_names)
