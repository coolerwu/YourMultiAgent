"""
adapter/worker_ws.py

WebSocket 端点 /ws/worker：
  Remote Worker 连接后先发送 register 消息声明自己的 capabilities，
  之后持续接收 result 消息（对应 Server 发起的 invoke 请求的返回值）。

协议：
  Client → Server: {"type": "register", "worker_id": "my-mac", "capabilities": [...]}
  Server → Client: {"type": "registered"}
  Server → Client: {"type": "invoke", "request_id": "uuid", "capability": "...",
                    "params": {...}, "context": {...}}
  Client → Server: {"type": "result", "request_id": "uuid", "result": ..., "error": null}
"""

import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from server.container import get_worker_router
from server.domain.worker.capability_entity import CapabilityEntity, ParameterSchema
from server.domain.worker.worker_entity import WorkerMetaEntity
from server.infra.worker.remote_worker_proxy import RemoteWorkerProxy
from server.infra.worker.worker_router import WorkerRouter
from server.support.page_auth import extract_bearer_token, load_auth_settings, verify_token
from server.support.app_logging import get_logger, log_context, log_event

router = APIRouter(tags=["WorkerWS"])
logger = get_logger(__name__)


@router.websocket("/ws/worker")
async def worker_ws(
    ws: WebSocket,
    worker_router: WorkerRouter = Depends(get_worker_router),
) -> None:
    request_id = ws.headers.get("x-request-id", "").strip() or str(uuid.uuid4())
    if load_auth_settings().enabled:
        token = ws.query_params.get("token", "") or extract_bearer_token(ws.headers.get("authorization", ""))
        if not verify_token(token):
            await ws.close(code=1008)
            return
    await ws.accept()
    proxy: RemoteWorkerProxy | None = None

    with log_context(request_id=request_id):
        log_event(logger, event="ws_connected", layer="ws", action="worker_session", status="started")
        try:
            # 第一条消息必须是 register
            msg = await ws.receive_json()
            if msg.get("type") != "register":
                log_event(
                    logger,
                    event="worker_register_rejected",
                    layer="ws",
                    action="worker_session",
                    status="client_error",
                    extra={"reason": "首条消息必须是 register"},
                )
                await ws.send_json({"type": "error", "message": "首条消息必须是 register"})
                await ws.close()
                return

            worker_id = msg.get("worker_id", "unknown")
            raw_caps = msg.get("capabilities", [])
            capabilities = [_cap_from_dict(c) for c in raw_caps]
            raw_meta = msg.get("worker_meta", {})
            meta = WorkerMetaEntity(
                worker_id=worker_id,
                kind=raw_meta.get("kind", "generic"),
                label=raw_meta.get("label", worker_id),
                version=raw_meta.get("version", ""),
                platform=raw_meta.get("platform", ""),
                browser_type=raw_meta.get("browser_type", ""),
                headless=raw_meta.get("headless", True),
                allowed_origins=raw_meta.get("allowed_origins", []),
                max_sessions=raw_meta.get("max_sessions", 0),
                max_screenshot_bytes=raw_meta.get("max_screenshot_bytes", 0),
                max_text_chars=raw_meta.get("max_text_chars", 0),
                max_html_chars=raw_meta.get("max_html_chars", 0),
                source=f"{ws.client.host}:{ws.client.port}" if ws.client else "",
            )

            with log_context(worker_id=worker_id):
                proxy = RemoteWorkerProxy(worker_id, capabilities, ws, meta=meta)
                worker_router.register_remote(proxy)
                log_event(
                    logger,
                    event="worker_registered",
                    layer="ws",
                    action="worker_session",
                    status="success",
                    extra={"capabilities_count": len(capabilities)},
                )
                await ws.send_json({
                    "type": "registered",
                    "worker_id": worker_id,
                    "capabilities_count": len(capabilities),
                    "enabled_capabilities_count": len(proxy.list_capabilities()),
                })

                # 持续接收 result 消息
                async for data in ws.iter_json():
                    if data.get("type") == "result":
                        log_event(
                            logger,
                            event="worker_result_received",
                            layer="ws",
                            action="worker_session",
                            status="success",
                            extra={"request_id": data.get("request_id", "")},
                        )
                        proxy.resolve(
                            request_id=data["request_id"],
                            result=data.get("result"),
                            error=data.get("error"),
                        )
                    else:
                        proxy.mark_seen()

        except WebSocketDisconnect:
            log_event(logger, event="ws_disconnected", layer="ws", action="worker_session", status="disconnected")
        finally:
            if proxy is not None:
                with log_context(worker_id=proxy.worker_id):
                    worker_router.unregister_remote(proxy.worker_id)


# ── 辅助函数 ──────────────────────────────────────────────────

def _cap_from_dict(d: dict) -> CapabilityEntity:
    """将 JSON 中的 capability 描述还原为 CapabilityEntity"""
    params = [
        ParameterSchema(
            name=p["name"],
            type=p.get("type", "string"),
            description=p.get("description", ""),
            required=p.get("required", True),
            default=p.get("default"),
        )
        for p in d.get("parameters", [])
    ]
    return CapabilityEntity(
        name=d["name"],
        description=d.get("description", ""),
        parameters=params,
        worker_id=d.get("worker_id", "remote"),
        category=d.get("category", "general"),
        risk_level=d.get("risk_level", "low"),
        requires_session=d.get("requires_session", False),
        description_for_model=d.get("description_for_model", ""),
    )
