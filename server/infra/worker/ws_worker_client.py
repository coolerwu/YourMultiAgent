"""
infra/worker/ws_worker_client.py

WsWorkerClient：在远程机器上运行，通过 WebSocket 连接到 Central Server。

工作流：
  1. 扫描本机 @capability 注册函数
  2. 连接 ws://SERVER/ws/worker，发送 register 消息
  3. 持续接收 invoke 消息，调用本机 registry.invoke()，返回 result

由 `yourmultiagent worker` CLI 命令启动。
"""

import asyncio
import dataclasses
import json
import logging
from typing import Any

import websockets

from server.domain.worker.entity.capability_entity import CapabilityEntity
from server.infra.worker import registry
from server.infra.worker.registry import scan_handlers

logger = logging.getLogger(__name__)


class WsWorkerClient:
    def __init__(self, server_url: str, worker_name: str) -> None:
        # server_url 格式：ws://host:port 或 wss://host:port
        # 自动补全路径
        base = server_url.rstrip("/")
        self._ws_url = f"{base}/ws/worker"
        self._name = worker_name

    async def start(self) -> None:
        """扫描 capabilities 并连接 Server，断线自动重连。"""
        scan_handlers()
        caps = registry.get_all_capabilities()
        logger.info("Worker '%s' 已加载 %d 个 capabilities", self._name, len(caps))

        while True:
            try:
                await self._run(caps)
            except (websockets.ConnectionClosed, OSError) as e:
                logger.warning("连接断开（%s），5 秒后重连...", e)
                await asyncio.sleep(5)
            except Exception as e:
                logger.error("意外错误：%s，5 秒后重连...", e)
                await asyncio.sleep(5)

    async def _run(self, caps: list[CapabilityEntity]) -> None:
        logger.info("连接 %s ...", self._ws_url)
        async with websockets.connect(self._ws_url) as ws:
            # 发送 register
            await ws.send(json.dumps({
                "type": "register",
                "worker_id": self._name,
                "worker_meta": {
                    "kind": "generic",
                    "label": self._name,
                    "version": "1.0.0",
                    "platform": "",
                },
                "capabilities": [_cap_to_dict(c) for c in caps],
            }))

            resp = json.loads(await ws.recv())
            if resp.get("type") != "registered":
                raise RuntimeError(f"注册失败: {resp}")
            logger.info("已注册到 Server，capabilities: %d", resp.get("capabilities_count", 0))

            # 处理 invoke 消息
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("type") == "invoke":
                    await self._handle_invoke(ws, msg)

    async def _handle_invoke(self, ws: Any, msg: dict) -> None:
        request_id = msg["request_id"]
        cap_name = msg["capability"]
        params = msg.get("params", {})
        context = msg.get("context")

        try:
            result = await registry.invoke(cap_name, params, context)
            await ws.send(json.dumps({
                "type": "result",
                "request_id": request_id,
                "result": result,
                "error": None,
            }))
        except Exception as e:
            await ws.send(json.dumps({
                "type": "result",
                "request_id": request_id,
                "result": None,
                "error": str(e),
            }))


# ── 辅助函数 ──────────────────────────────────────────────────

def _cap_to_dict(cap: CapabilityEntity) -> dict:
    """将 CapabilityEntity 序列化为 JSON 友好的 dict"""
    return dataclasses.asdict(cap)
