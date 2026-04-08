"""
infra/worker/worker_router.py

WorkerRouter：实现 WorkerGateway，聚合本机 LocalWorker + 所有远程 Worker 的 capabilities，
并将 invoke() 调用路由到持有该 capability 的 Worker。

路由规则：
  - 本机 LocalWorker 优先（capability 重名时本机胜出）
  - Remote Worker 按注册顺序首匹配
  - 两者都没有时抛出 ValueError
"""

from pathlib import Path
from typing import Any

from server.domain.worker.entity.capability_entity import CapabilityEntity
from server.domain.worker.entity.worker_entity import WorkerInfoEntity
from server.domain.worker.gateway.worker_gateway import WorkerGateway
from server.infra.store.workspace_json import read_json, write_json
from server.infra.worker.local_worker import LocalWorker
from server.infra.worker.remote_worker_proxy import RemoteWorkerProxy


class WorkerRouter(WorkerGateway):
    def __init__(self, local: LocalWorker, data_dir: Path | None = None) -> None:
        self._local = local
        # 保序字典，按注册顺序首匹配
        self._remotes: dict[str, RemoteWorkerProxy] = {}
        self._data_dir = data_dir
        self._enabled_configs = self._load_enabled_configs()

    # ── 远程 Worker 注册管理（由 worker_ws.py 调用）─────────

    def register_remote(self, proxy: RemoteWorkerProxy) -> None:
        enabled = self._enabled_configs.get(proxy.worker_id)
        if enabled is not None:
            proxy.set_enabled_capabilities(proxy.worker_id, enabled)
        self._remotes[proxy.worker_id] = proxy

    def unregister_remote(self, worker_id: str) -> None:
        self._remotes.pop(worker_id, None)

    def list_remote_workers(self) -> list[str]:
        return list(self._remotes.keys())

    # ── WorkerGateway 实现 ────────────────────────────────────

    def list_capabilities(self) -> list[CapabilityEntity]:
        """合并本机 + 所有远程已授权 capabilities（同名时本机优先，不去重）"""
        caps = list(self._local.list_capabilities())
        for proxy in self._remotes.values():
            caps.extend(proxy.list_capabilities())
        return caps

    def list_workers(self) -> list[WorkerInfoEntity]:
        workers = list(self._local.list_workers())
        for proxy in self._remotes.values():
            workers.append(proxy.to_worker_info())
        return workers

    def set_enabled_capabilities(self, worker_id: str, capability_names: list[str]) -> WorkerInfoEntity:
        if worker_id == "local":
            return self._local.set_enabled_capabilities(worker_id, capability_names)

        proxy = self._remotes.get(worker_id)
        if proxy is None:
            raise ValueError(f"Worker 不存在: {worker_id}")

        info = proxy.set_enabled_capabilities(worker_id, capability_names)
        self._enabled_configs[worker_id] = list(info.enabled_capability_names)
        self._save_enabled_configs()
        return info

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

    def _enabled_config_path(self) -> Path | None:
        if self._data_dir is None:
            return None
        return self._data_dir / "worker_settings.json"

    def _load_enabled_configs(self) -> dict[str, list[str]]:
        path = self._enabled_config_path()
        if path is None:
            return {}
        raw = read_json(path, {"version": 1, "workers": {}})
        workers = raw.get("workers", {}) if isinstance(raw, dict) else {}
        if not isinstance(workers, dict):
            return {}
        result: dict[str, list[str]] = {}
        for worker_id, names in workers.items():
            if isinstance(worker_id, str) and isinstance(names, list):
                result[worker_id] = [item for item in names if isinstance(item, str)]
        return result

    def _save_enabled_configs(self) -> None:
        path = self._enabled_config_path()
        if path is None:
            return
        write_json(path, {"version": 1, "workers": self._enabled_configs})
