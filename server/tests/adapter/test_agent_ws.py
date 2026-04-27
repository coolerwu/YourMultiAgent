"""
tests/adapter/test_agent_ws.py

agent_ws WebSocket 端点测试：覆盖正常执行与首包校验失败。
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect

from server.adapter.agent_ws import router
from server.container import get_agent_service
from server.domain.agent.agent_entity import GlobalSettingsEntity, PageAuthConfigEntity
from server.infra.store.workspace_json import save_global_settings


class _AgentServiceStub:
    def __init__(self, events):
        self._events = events

    async def run_workspace(self, _workspace_id: str, _user_message: str, _session_id: str = ""):
        for event in self._events:
            yield event


def _build_app(service) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_agent_service] = lambda: service
    return app


def test_run_workspace_ws_streams_events():
    service = _AgentServiceStub([
        {"type": "coordinator_start", "node": "coordinator"},
        {"type": "text", "node": "coordinator", "content": "hello"},
        {"type": "done"},
    ])
    app = _build_app(service)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/workspaces/ws-1/run") as websocket:
            websocket.send_json({"user_message": "你好", "session_id": "session-1"})

            first = websocket.receive_json()
            second = websocket.receive_json()
            third = websocket.receive_json()

    assert first["type"] == "coordinator_start"
    assert second["type"] == "text"
    assert third["type"] == "done"


def test_run_workspace_ws_rejects_empty_user_message():
    service = _AgentServiceStub([])
    app = _build_app(service)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/workspaces/ws-1/run") as websocket:
            websocket.send_json({"user_message": "   "})
            error = websocket.receive_json()

    assert error == {"type": "error", "message": "user_message 不能为空"}


def test_run_workspace_ws_rejects_missing_auth_token(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    save_global_settings(
        tmp_path,
        GlobalSettingsEntity(
            page_auth=PageAuthConfigEntity(enabled=True, access_key="ak-demo", secret_key="sk-demo")
        ),
    )
    app = _build_app(_AgentServiceStub([]))

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws/workspaces/ws-1/run"):
                pass

    assert exc.value.code == 1008
