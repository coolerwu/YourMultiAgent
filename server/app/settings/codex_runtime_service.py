"""
app/settings/codex_runtime_service.py

Codex CLI 的安装、检测、登录状态管理服务。
"""

from __future__ import annotations

from dataclasses import dataclass

from server.domain.agent.entity.agent_entity import CodexConnectionEntity
from server.domain.agent.gateway.workspace_gateway import WorkspaceGateway
from server.infra.codex.codex_cli import (
    build_install_command,
    build_install_manual_command,
    detect_cli_version,
    detect_codex_path,
    detect_login_status,
    detect_node_path,
    detect_npm_path,
    now_iso,
    os_family,
    run_command,
)


@dataclass
class CodexActionResult:
    connection: CodexConnectionEntity
    message: str
    manual_command: str = ""
    details: str = ""


class CodexRuntimeService:
    def __init__(self, gateway: WorkspaceGateway) -> None:
        self._gateway = gateway

    async def enrich_connections(self, connections: list[CodexConnectionEntity]) -> list[CodexConnectionEntity]:
        return [self.inspect_connection(connection) for connection in connections]

    def inspect_connection(self, connection: CodexConnectionEntity) -> CodexConnectionEntity:
        codex_path = detect_codex_path()
        npm_path = detect_npm_path()
        enriched = _copy_connection(connection)
        enriched.os_family = os_family()
        enriched.last_checked_at = now_iso()
        enriched.install_path = codex_path
        enriched.cli_version = detect_cli_version(codex_path)

        if codex_path:
            enriched.install_status = "installed"
        elif npm_path:
            enriched.install_status = "not_installed"
        else:
            enriched.install_status = "missing_prerequisite"
            enriched.last_error = "未检测到 npm，无法自动安装 Codex CLI。"

        login_status, details = detect_login_status(codex_path)
        enriched.login_status = login_status
        if login_status == "connected":
            enriched.status = "connected"
            enriched.last_error = ""
            enriched.last_verified_at = now_iso()
            enriched.account_label = connection.account_label or "ChatGPT"
        elif enriched.install_status == "installed":
            enriched.status = "disconnected"
            if login_status == "error":
                enriched.last_error = details or "Codex 登录状态检测失败。"
        else:
            enriched.status = "disconnected"
        return enriched

    async def refresh_connection(self, connection_id: str) -> CodexActionResult:
        connection = await self._load_connection(connection_id)
        refreshed = self.inspect_connection(connection)
        await self._save_connection(refreshed)
        return CodexActionResult(connection=refreshed, message="Codex 运行时状态已刷新")

    async def install_connection(self, connection_id: str) -> CodexActionResult:
        connection = await self._load_connection(connection_id)
        current = self.inspect_connection(connection)
        if current.install_status == "installed":
            await self._save_connection(current)
            return CodexActionResult(connection=current, message="Codex CLI 已安装")

        if not detect_node_path() or not detect_npm_path():
            current.install_status = "missing_prerequisite"
            current.status = "disconnected"
            current.last_error = "未检测到 Node.js/npm，请先在宿主机安装 Node.js 后再安装 Codex。"
            await self._save_connection(current)
            return CodexActionResult(
                connection=current,
                message=current.last_error,
                manual_command=build_install_manual_command(),
            )

        result = run_command(build_install_command(), timeout=300)
        refreshed = self.inspect_connection(current)
        refreshed.last_error = "" if refreshed.install_status == "installed" else (result.combined_output or "Codex CLI 安装失败")
        await self._save_connection(refreshed)
        return CodexActionResult(
            connection=refreshed,
            message="Codex CLI 安装完成" if refreshed.install_status == "installed" else "Codex CLI 安装失败",
            manual_command="" if refreshed.install_status == "installed" else build_install_manual_command(),
            details=result.combined_output,
        )

    async def login_connection(self, connection_id: str) -> CodexActionResult:
        connection = await self._load_connection(connection_id)
        current = self.inspect_connection(connection)
        if current.install_status != "installed":
            await self._save_connection(current)
            return CodexActionResult(
                connection=current,
                message="请先安装 Codex CLI",
                manual_command=build_install_manual_command(),
            )

        if current.login_status == "connected":
            await self._save_connection(current)
            return CodexActionResult(connection=current, message="Codex 已登录")

        current.last_error = ""
        await self._save_connection(current)
        return CodexActionResult(
            connection=current,
            message="请在宿主机执行 Codex 登录命令完成授权",
            manual_command="codex login --device-auth",
        )

    async def runtime_summary(self) -> dict:
        codex_path = detect_codex_path()
        return {
            "os_family": os_family(),
            "node_path": detect_node_path(),
            "npm_path": detect_npm_path(),
            "codex_path": codex_path,
            "codex_version": detect_cli_version(codex_path),
        }

    async def _load_connection(self, connection_id: str) -> CodexConnectionEntity:
        settings = await self._gateway.load_global_settings()
        connection = next((item for item in settings.codex_connections if item.id == connection_id), None)
        if connection is None:
            raise ValueError(f"Codex 连接不存在: {connection_id}")
        return connection

    async def _save_connection(self, connection: CodexConnectionEntity) -> None:
        settings = await self._gateway.load_global_settings()
        settings.codex_connections = [
            connection if item.id == connection.id else item
            for item in settings.codex_connections
        ]
        await self._gateway.save_global_settings(settings)


def _copy_connection(connection: CodexConnectionEntity) -> CodexConnectionEntity:
    return CodexConnectionEntity(
        id=connection.id,
        name=connection.name,
        provider=connection.provider,
        auth_mode=connection.auth_mode,
        account_label=connection.account_label,
        status=connection.status,
        credential_ref=connection.credential_ref,
        last_verified_at=connection.last_verified_at,
        install_status=connection.install_status,
        install_path=connection.install_path,
        login_status=connection.login_status,
        last_checked_at=connection.last_checked_at,
        last_error=connection.last_error,
        cli_version=connection.cli_version,
        os_family=connection.os_family,
    )
