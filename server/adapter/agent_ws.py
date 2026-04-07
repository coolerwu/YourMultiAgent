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

import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from server.app.agent.agent_app_service import AgentAppService
from server.container import get_agent_service

router = APIRouter(tags=["AgentWS"])


@router.websocket("/ws/workspaces/{workspace_id}/run")
async def run_workspace_ws(
    workspace_id: str,
    ws: WebSocket,
    svc: AgentAppService = Depends(get_agent_service),
) -> None:
    await ws.accept()
    try:
        # 接收第一条消息（含 user_message）
        raw = await ws.receive_json()
        user_message = raw.get("user_message", "").strip()
        session_id = raw.get("session_id", "").strip()
        if not user_message:
            await ws.send_json({"type": "error", "message": "user_message 不能为空"})
            await ws.close()
            return

        # 流式转发 dict 事件
        async for event in svc.run_workspace(workspace_id, user_message, session_id):
            await ws.send_json(event)
            if event.get("type") == "done":
                break

    except ValueError as exc:
        await ws.send_json({"type": "error", "message": str(exc)})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await ws.send_json({"type": "error", "message": f"执行异常: {exc}"})
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
