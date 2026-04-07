"""
infra/worker/remote_worker_proxy.py

RemoteWorkerProxy：代表一个已通过 WebSocket 连接到 Central Server 的远程 Worker。

工作流：
  1. WebSocket 握手后，Server 创建此对象并将其注册到 WorkerRouter
  2. invoke() 发送 invoke 消息给远端，通过 asyncio.Future 等待结果
  3. 远端返回 result 消息后，worker_ws.py 调用 resolve() 恢复 Future
  4. WebSocket 断开时，从 WorkerRouter 注销
"""

import asyncio
import uuid
from typing import Any

from fastapi import WebSocket

from server.domain.worker.entity.capability_entity import CapabilityEntity
from server.domain.worker.gateway.worker_gateway import WorkerGateway


class RemoteWorkerProxy(WorkerGateway):
    def __init__(self, worker_id: str, capabilities: list[CapabilityEntity], ws: WebSocket) -> None:
        self.worker_id = worker_id
        self._capabilities = capabilities
        self._ws = ws
        self._pending: dict[str, asyncio.Future] = {}

    # ── WorkerGateway 实现 ────────────────────────────────────

    def list_capabilities(self) -> list[CapabilityEntity]:
        return list(self._capabilities)

    async def invoke(
        self,
        capability_name: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Any:
        request_id = str(uuid.uuid4())
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[request_id] = future

        await self._ws.send_json({
            "type": "invoke",
            "request_id": request_id,
            "capability": capability_name,
            "params": params,
            "context": context or {},
        })

        try:
            return await asyncio.wait_for(future, timeout=60)
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            raise TimeoutError(f"Remote worker '{self.worker_id}' 调用 '{capability_name}' 超时（60s）")

    # ── 内部接口（由 worker_ws.py 调用）─────────────────────

    def resolve(self, request_id: str, result: Any, error: str | None) -> None:
        """收到远端 result 消息后调用，解除 invoke() 的等待。"""
        future = self._pending.pop(request_id, None)
        if future is None or future.done():
            return
        if error:
            future.set_exception(RuntimeError(f"Remote capability error: {error}"))
        else:
            future.set_result(result)
