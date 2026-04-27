"""
adapter/agent_ws.py

WebSocket 端点 /ws/workspaces/{workspace_id}/run：
  接收用户消息，流式返回 Workspace 单编排执行事件。

协议（单次会话）：
  Client → Server: {"user_message": "请帮我分析这份文件"}
  Server → Client: {"type": "node_start", "node": "agent1", "node_name": "分析师"}
  Server → Client: {"type": "text",       "node": "agent1", "content": "..."}
  Server → Client: {"type": "tool_start", "node": "agent1", "tool": "read_file"}
  Server → Client: {"type": "tool_end",   "node": "agent1", "tool": "read_file", "result": "..."}
  Server → Client: {"type": "node_end",   "node": "agent1"}
  Server → Client: {"type": "done"}
  连接由 Server 在发完 done 后关闭。

错误处理：
  - Workspace 不存在或 user_message 缺失 → 发送 {"type": "error", "message": "..."} 后关闭
  - 执行过程异常 → 同上
"""

import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from server.app.agent.agent_app_service import AgentAppService
from server.container import get_agent_service
from server.support.page_auth import extract_bearer_token, load_auth_settings, verify_token
from server.support.app_logging import get_logger, log_context, log_event

router = APIRouter(tags=["AgentWS"])
logger = get_logger(__name__)


@router.websocket("/ws/workspaces/{workspace_id}/run")
async def run_workspace_ws(
    workspace_id: str,
    ws: WebSocket,
    svc: AgentAppService = Depends(get_agent_service),
) -> None:
    request_id = ws.headers.get("x-request-id", "").strip() or str(uuid.uuid4())
    if load_auth_settings().enabled:
        token = ws.query_params.get("token", "") or extract_bearer_token(ws.headers.get("authorization", ""))
        if not verify_token(token):
            await ws.close(code=1008)
            return
    await ws.accept()
    with log_context(request_id=request_id, workspace_id=workspace_id):
        log_event(logger, event="ws_connected", layer="ws", action="workspace_run", status="started")
        try:
            # 接收第一条消息（含 user_message）
            raw = await ws.receive_json()
            user_message = raw.get("user_message", "").strip()
            session_id = raw.get("session_id", "").strip()
            if not user_message:
                log_event(
                    logger,
                    event="ws_invalid_payload",
                    layer="ws",
                    action="workspace_run",
                    status="client_error",
                    extra={"reason": "user_message 不能为空"},
                )
                await ws.send_json({"type": "error", "message": "user_message 不能为空"})
                await ws.close()
                return

            if session_id:
                with log_context(session_id=session_id):
                    log_event(
                        logger,
                        event="workspace_run_started",
                        layer="ws",
                        action="workspace_run",
                        status="started",
                    )
                    async for event in svc.run_workspace(workspace_id, user_message, session_id):
                        await ws.send_json(event)
                        if event.get("type") == "done":
                            break
            else:
                log_event(
                    logger,
                    event="workspace_run_started",
                    layer="ws",
                    action="workspace_run",
                    status="started",
                )
                async for event in svc.run_workspace(workspace_id, user_message, session_id):
                    await ws.send_json(event)
                    if event.get("type") == "done":
                        break

            log_event(logger, event="workspace_run_finished", layer="ws", action="workspace_run", status="success")

        except ValueError as exc:
            log_event(
                logger,
                event="workspace_run_error",
                layer="ws",
                action="workspace_run",
                status="error",
                level=40,
                extra={"error": str(exc)},
            )
            await ws.send_json({"type": "error", "message": str(exc)})
        except WebSocketDisconnect:
            log_event(logger, event="ws_disconnected", layer="ws", action="workspace_run", status="disconnected")
        except Exception as exc:
            log_event(
                logger,
                event="workspace_run_error",
                layer="ws",
                action="workspace_run",
                status="error",
                level=40,
                extra={"error": str(exc)},
            )
            try:
                await ws.send_json({"type": "error", "message": f"执行异常: {exc}"})
            except Exception:
                pass
        finally:
            try:
                await ws.close()
            except Exception:
                pass
