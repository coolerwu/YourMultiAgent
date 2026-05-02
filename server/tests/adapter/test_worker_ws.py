"""
tests/adapter/test_worker_ws.py

worker_ws WebSocket 端点测试：覆盖注册成功与首包非法。
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect

from server.adapter.worker_ws import router
from server.container import get_worker_router
from server.domain.agent.agent_entity import GlobalSettingsEntity, PageAuthConfigEntity
from server.infra.store.workspace_json import save_global_settings


@pytest.fixture(autouse=True)
def _disable_page_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    save_global_settings(
        tmp_path,
        GlobalSettingsEntity(page_auth=PageAuthConfigEntity(enabled=False)),
    )


class _WorkerRouterStub:
    def __init__(self):
        self.registered = []
        self.unregistered = []

    def register_remote(self, proxy) -> None:
        self.registered.append(proxy)

    def unregister_remote(self, worker_id: str) -> None:
        self.unregistered.append(worker_id)


def _build_app(worker_router) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_worker_router] = lambda: worker_router
    return app


def test_worker_ws_registers_and_unregisters_remote_worker():
    worker_router = _WorkerRouterStub()
    app = _build_app(worker_router)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/worker") as websocket:
            websocket.send_json({
                "type": "register",
                "worker_id": "browser-1",
                "capabilities": [
                    {
                        "name": "browser_open",
                        "description": "open browser",
                        "parameters": [],
                    }
                ],
                "worker_meta": {
                    "kind": "browser",
                    "label": "Browser Worker",
                },
            })
            registered = websocket.receive_json()

    assert registered["type"] == "registered"
    assert registered["worker_id"] == "browser-1"
    assert registered["capabilities_count"] == 1
    assert len(worker_router.registered) == 1
    assert worker_router.unregistered == ["browser-1"]


def test_worker_ws_rejects_non_register_first_message():
    worker_router = _WorkerRouterStub()
    app = _build_app(worker_router)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/worker") as websocket:
            websocket.send_json({"type": "result", "request_id": "req-1"})
            error = websocket.receive_json()

    assert error == {"type": "error", "message": "首条消息必须是 register"}
    assert worker_router.registered == []


def test_worker_ws_rejects_missing_auth_token(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    save_global_settings(
        tmp_path,
        GlobalSettingsEntity(
            page_auth=PageAuthConfigEntity(enabled=True, access_key="ak-demo", secret_key="sk-demo")
        ),
    )
    app = _build_app(_WorkerRouterStub())

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws/worker"):
                pass

    assert exc.value.code == 1008
