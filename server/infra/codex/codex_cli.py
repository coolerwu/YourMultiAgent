"""
infra/codex/codex_cli.py

Codex CLI 相关的系统探测、命令构造与进程执行辅助。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone


CODEX_PACKAGE = "@openai/codex"


@dataclass
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def combined_output(self) -> str:
        return "\n".join(part for part in [self.stdout.strip(), self.stderr.strip()] if part).strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def os_family() -> str:
    if sys.platform.startswith("darwin"):
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    return "unknown"


def codex_command_name() -> str:
    return "codex.cmd" if os_family() == "windows" else "codex"


def npm_command_name() -> str:
    return "npm.cmd" if os_family() == "windows" else "npm"


def detect_codex_path() -> str:
    return shutil.which(codex_command_name()) or ""


def detect_node_path() -> str:
    return shutil.which("node") or ""


def detect_npm_path() -> str:
    return shutil.which(npm_command_name()) or ""


def build_install_command() -> list[str]:
    return [npm_command_name(), "install", "-g", CODEX_PACKAGE]


def run_command(args: list[str], timeout: int = 30, cwd: str = "") -> CommandResult:
    env = os.environ.copy()
    env.setdefault("OTEL_SDK_DISABLED", "true")
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd or None,
        env=env,
    )
    return CommandResult(
        args=args,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def detect_cli_version(codex_path: str) -> str:
    if not codex_path:
        return ""
    result = run_command([codex_path, "--version"], timeout=15)
    if result.returncode != 0:
        return ""
    for line in result.combined_output.splitlines():
        line = line.strip()
        if line.lower().startswith("codex"):
            parts = line.split()
            if len(parts) >= 2:
                return parts[-1]
    return result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""


def detect_login_status(codex_path: str) -> tuple[str, str]:
    if not codex_path:
        return "unknown", ""

    result = run_command([codex_path, "login", "status"], timeout=20)
    output = result.combined_output
    lowered = output.lower()
    if result.returncode != 0:
        return "error", output
    if "logged in" in lowered:
        return "connected", output
    if "not logged" in lowered or "logged out" in lowered:
        return "disconnected", output
    return "unknown", output
