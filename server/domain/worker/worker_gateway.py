"""
domain/worker/worker_gateway.py

Worker 调用的抽象接口。
domain 层通过此接口调用 capability，不感知本机/远程差异。
"""

from abc import ABC, abstractmethod
from typing import Any

from server.domain.worker.capability_entity import CapabilityEntity
from server.domain.worker.worker_entity import WorkerInfoEntity


class WorkerGateway(ABC):
    """Worker 能力调用接口"""

    @abstractmethod
    def list_capabilities(self) -> list[CapabilityEntity]:
        """返回当前 Worker 支持的所有能力"""
        ...

    @abstractmethod
    def list_workers(self) -> list[WorkerInfoEntity]:
        """返回当前在线 Worker 列表及其授权状态"""
        ...

    @abstractmethod
    def set_enabled_capabilities(self, worker_id: str, capability_names: list[str]) -> WorkerInfoEntity:
        """更新某个 Worker 的已授权能力集"""
        ...

    @abstractmethod
    async def invoke(
        self,
        capability_name: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Any:
        """
        调用指定能力，返回执行结果。
        context 用于注入运行时信息，如 {"work_dir": "/abs/path/agentA/"}
        """
        ...
