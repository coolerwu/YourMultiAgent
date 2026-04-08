from unittest.mock import AsyncMock, MagicMock

import pytest

from server.app.settings.codex_runtime_service import CodexRuntimeService
from server.domain.agent.agent_entity import CodexConnectionEntity, GlobalSettingsEntity


def _make_gateway(connection: CodexConnectionEntity):
    gw = MagicMock()
    settings = GlobalSettingsEntity(codex_connections=[connection])
    gw.load_global_settings = AsyncMock(return_value=settings)
    gw.save_global_settings = AsyncMock(side_effect=lambda value: value)
    return gw


@pytest.mark.asyncio
async def test_refresh_connection_marks_installed_and_connected(monkeypatch):
    connection = CodexConnectionEntity(id="codex-1", name="个人 Codex")
    svc = CodexRuntimeService(_make_gateway(connection))

    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_codex_path", lambda: "/usr/local/bin/codex")
    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_npm_path", lambda: "/usr/local/bin/npm")
    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_node_path", lambda: "/usr/local/bin/node")
    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_cli_version", lambda _path: "0.1.0")
    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_login_status", lambda _path: ("connected", "Logged in using ChatGPT"))

    result = await svc.refresh_connection("codex-1")

    assert result.connection.install_status == "installed"
    assert result.connection.login_status == "connected"
    assert result.connection.status == "connected"


@pytest.mark.asyncio
async def test_install_connection_returns_manual_command_when_node_missing(monkeypatch):
    connection = CodexConnectionEntity(id="codex-1", name="个人 Codex")
    svc = CodexRuntimeService(_make_gateway(connection))

    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_codex_path", lambda: "")
    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_npm_path", lambda: "")
    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_node_path", lambda: "")
    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_cli_version", lambda _path: "")
    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_login_status", lambda _path: ("unknown", ""))

    result = await svc.install_connection("codex-1")

    assert "npm install -g @openai/codex --prefix" in result.manual_command
    assert result.connection.install_status == "missing_prerequisite"


@pytest.mark.asyncio
async def test_login_connection_returns_manual_command(monkeypatch):
    connection = CodexConnectionEntity(id="codex-1", name="个人 Codex")
    svc = CodexRuntimeService(_make_gateway(connection))

    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_codex_path", lambda: "/usr/local/bin/codex")
    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_npm_path", lambda: "/usr/local/bin/npm")
    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_node_path", lambda: "/usr/local/bin/node")
    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_cli_version", lambda _path: "0.1.0")
    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_login_status", lambda _path: ("disconnected", "Not logged in"))

    result = await svc.login_connection("codex-1")

    assert result.manual_command == "codex login --device-auth"
    assert "宿主机" in result.message


@pytest.mark.asyncio
async def test_install_connection_returns_login_hint_after_success(monkeypatch):
    connection = CodexConnectionEntity(id="codex-1", name="个人 Codex")
    svc = CodexRuntimeService(_make_gateway(connection))
    installed = {"value": False}

    monkeypatch.setattr(
        "server.app.settings.codex_runtime_service.detect_codex_path",
        lambda: "/home/qiuqiu/.local/bin/codex" if installed["value"] else "",
    )
    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_npm_path", lambda: "/usr/bin/npm")
    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_node_path", lambda: "/usr/bin/node")
    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_cli_version", lambda _path: "0.1.0")
    monkeypatch.setattr("server.app.settings.codex_runtime_service.detect_login_status", lambda _path: ("disconnected", "Not logged in"))

    def fake_run_command(_args, timeout=300):
        installed["value"] = True
        return type("Result", (), {"combined_output": "installed"})()

    monkeypatch.setattr("server.app.settings.codex_runtime_service.run_command", fake_run_command)

    result = await svc.install_connection("codex-1")

    assert result.manual_command == "codex login --device-auth"
    assert "退出终端并重新进入" in result.message
