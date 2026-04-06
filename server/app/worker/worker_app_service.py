"""
app/worker/worker_app_service.py

Worker 应用服务：查询已注册的 capability 列表。
"""

from server.domain.worker.entity.capability_entity import CapabilityEntity
from server.domain.worker.gateway.worker_gateway import WorkerGateway


class WorkerAppService:
    def __init__(self, worker: WorkerGateway) -> None:
        self._worker = worker

    def list_capabilities(self) -> list[CapabilityEntity]:
        return self._worker.list_capabilities()
