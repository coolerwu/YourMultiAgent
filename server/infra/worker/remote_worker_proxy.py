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
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

from server.domain.worker.capability_entity import CapabilityEntity
from server.domain.worker.worker_entity import WorkerInfoEntity, WorkerMetaEntity
from server.domain.worker.worker_gateway import WorkerGateway
from server.support.app_logging import get_logger, log_event

logger = get_logger(__name__)


class RemoteWorkerProxy(WorkerGateway):
    def __init__(
        self,
        worker_id: str,
        capabilities: list[CapabilityEntity],
        ws: WebSocket,
        meta: WorkerMetaEntity | None = None,
        enabled_capability_names: list[str] | None = None,
    ) -> None:
        self.worker_id = worker_id
        self._capabilities = capabilities
        self._ws = ws
        self._pending: dict[str, asyncio.Future] = {}
        self._meta = meta or WorkerMetaEntity(worker_id=worker_id, kind="generic", label=worker_id)
        self._enabled_capability_names = enabled_capability_names or [item.name for item in capabilities]
        self._connected_at = self._now_iso()
        self._last_seen_at = self._connected_at
        self._last_error = ""

    # ── WorkerGateway 实现 ────────────────────────────────────

    def list_capabilities(self) -> list[CapabilityEntity]:
        enabled = set(self._enabled_capability_names)
        return [item for item in self._capabilities if item.name in enabled]

    def list_registered_capabilities(self) -> list[CapabilityEntity]:
        return list(self._capabilities)

    def list_workers(self) -> list[WorkerInfoEntity]:
        return [self.to_worker_info()]

    def set_enabled_capabilities(self, worker_id: str, capability_names: list[str]) -> WorkerInfoEntity:
        if worker_id != self.worker_id:
            raise ValueError(f"Worker 不存在: {worker_id}")
        available = {item.name for item in self._capabilities}
        self._enabled_capability_names = [item for item in capability_names if item in available]
        log_event(
            logger,
            event="remote_worker_capabilities_updated",
            layer="worker",
            action="set_enabled_capabilities",
            status="success",
            worker_id=self.worker_id,
            extra={"enabled_capability_names": list(self._enabled_capability_names)},
        )
        return self.to_worker_info()

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
        started_at = asyncio.get_event_loop().time()

        await self._ws.send_json({
            "type": "invoke",
            "request_id": request_id,
            "capability": capability_name,
            "params": params,
            "context": context or {},
        })
        log_event(
            logger,
            event="remote_worker_invoke_sent",
            layer="worker",
            action="invoke_remote",
            status="started",
            request_id=request_id,
            worker_id=self.worker_id,
            extra={"capability_name": capability_name},
        )

        try:
            result = await asyncio.wait_for(future, timeout=60)
            log_event(
                logger,
                event="remote_worker_invoke_finished",
                layer="worker",
                action="invoke_remote",
                status="success",
                request_id=request_id,
                worker_id=self.worker_id,
                duration_ms=int((asyncio.get_event_loop().time() - started_at) * 1000),
                extra={"capability_name": capability_name},
            )
            return result
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            log_event(
                logger,
                event="remote_worker_invoke_timeout",
                layer="worker",
                action="invoke_remote",
                status="error",
                level=40,
                request_id=request_id,
                worker_id=self.worker_id,
                duration_ms=int((asyncio.get_event_loop().time() - started_at) * 1000),
                extra={"capability_name": capability_name},
            )
            raise TimeoutError(f"Remote worker '{self.worker_id}' 调用 '{capability_name}' 超时（60s）")

    # ── 内部接口（由 worker_ws.py 调用）─────────────────────

    def resolve(self, request_id: str, result: Any, error: str | None) -> None:
        """收到远端 result 消息后调用，解除 invoke() 的等待。"""
        self.mark_seen()
        future = self._pending.pop(request_id, None)
        if future is None or future.done():
            return
        if error:
            self._last_error = error
            log_event(
                logger,
                event="remote_worker_result_error",
                layer="worker",
                action="resolve_remote_result",
                status="error",
                level=40,
                request_id=request_id,
                worker_id=self.worker_id,
                extra={"error": error},
            )
            future.set_exception(RuntimeError(f"Remote capability error: {error}"))
        else:
            self._last_error = ""
            log_event(
                logger,
                event="remote_worker_result_ok",
                layer="worker",
                action="resolve_remote_result",
                status="success",
                request_id=request_id,
                worker_id=self.worker_id,
            )
            future.set_result(result)

    def mark_seen(self) -> None:
        self._last_seen_at = self._now_iso()

    def to_worker_info(self) -> WorkerInfoEntity:
        return WorkerInfoEntity(
            worker_id=self.worker_id,
            label=self._meta.label or self.worker_id,
            kind=self._meta.kind or "generic",
            status="online",
            registered_capabilities=self.list_registered_capabilities(),
            enabled_capability_names=list(self._enabled_capability_names),
            version=self._meta.version,
            platform=self._meta.platform,
            browser_type=self._meta.browser_type,
            headless=self._meta.headless,
            allowed_origins=list(self._meta.allowed_origins),
            max_sessions=self._meta.max_sessions,
            max_screenshot_bytes=self._meta.max_screenshot_bytes,
            max_text_chars=self._meta.max_text_chars,
            max_html_chars=self._meta.max_html_chars,
            source=self._meta.source,
            connected_at=self._connected_at,
            last_seen_at=self._last_seen_at,
            last_error=self._last_error,
        )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(UTC).isoformat()
