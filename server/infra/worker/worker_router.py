"""
infra/worker/worker_router.py

WorkerRouter：实现 WorkerGateway，聚合本机 LocalWorker + 所有远程 Worker 的 capabilities，
并将 invoke() 调用路由到持有该 capability 的 Worker。

路由规则：
  - 本机 LocalWorker 优先（capability 重名时本机胜出）
  - Remote Worker 按注册顺序首匹配
  - 两者都没有时抛出 ValueError
"""

from typing import Any

from server.domain.worker.entity.capability_entity import CapabilityEntity
from server.domain.worker.gateway.worker_gateway import WorkerGateway
from server.infra.worker.local_worker import LocalWorker
from server.infra.worker.remote_worker_proxy import RemoteWorkerProxy


class WorkerRouter(WorkerGateway):
    def __init__(self, local: LocalWorker) -> None:
        self._local = local
        # 保序字典，按注册顺序首匹配
        self._remotes: dict[str, RemoteWorkerProxy] = {}

    # ── 远程 Worker 注册管理（由 worker_ws.py 调用）─────────

    def register_remote(self, proxy: RemoteWorkerProxy) -> None:
        self._remotes[proxy.worker_id] = proxy

    def unregister_remote(self, worker_id: str) -> None:
        self._remotes.pop(worker_id, None)

    def list_remote_workers(self) -> list[str]:
        return list(self._remotes.keys())

    # ── WorkerGateway 实现 ────────────────────────────────────

    def list_capabilities(self) -> list[CapabilityEntity]:
        """合并本机 + 所有远程 capabilities（同名时本机优先，不去重）"""
        caps = list(self._local.list_capabilities())
        for proxy in self._remotes.values():
            caps.extend(proxy.list_capabilities())
        return caps

    async def invoke(
        self,
        capability_name: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Any:
        # 本机优先
        local_names = {c.name for c in self._local.list_capabilities()}
        if capability_name in local_names:
            return await self._local.invoke(capability_name, params, context)

        # 按注册顺序查找远程
        for proxy in self._remotes.values():
            remote_names = {c.name for c in proxy.list_capabilities()}
            if capability_name in remote_names:
                return await proxy.invoke(capability_name, params, context)

        raise ValueError(f"没有任何 Worker 支持 capability: '{capability_name}'")
