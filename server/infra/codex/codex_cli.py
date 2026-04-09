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
from pathlib import Path


CODEX_PACKAGE = "@openai/codex"
CODEX_ENV_DROP_PREFIXES = (
    "OPENAI_",
    "AZURE_OPENAI_",
)


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


def preferred_npm_prefix() -> str:
    if os_family() == "windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return str(Path(local_app_data) / "npm")
        return ""
    return str(Path.home() / ".local")


def preferred_bin_dir() -> str:
    prefix = preferred_npm_prefix()
    if not prefix:
        return ""
    if os_family() == "windows":
        return prefix
    return str(Path(prefix) / "bin")


def _candidate_codex_paths() -> list[str]:
    command = codex_command_name()
    candidates = []
    bin_dir = preferred_bin_dir()
    if bin_dir:
        candidates.append(str(Path(bin_dir) / command))
    if os_family() != "windows":
        candidates.append(str(Path.home() / ".npm-global" / "bin" / command))
    return candidates


def detect_codex_path() -> str:
    found = shutil.which(codex_command_name())
    if found:
        return found
    for candidate in _candidate_codex_paths():
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return ""


def detect_node_path() -> str:
    return shutil.which("node") or ""


def detect_npm_path() -> str:
    return shutil.which(npm_command_name()) or ""


def build_install_command() -> list[str]:
    prefix = preferred_npm_prefix()
    cmd = [npm_command_name(), "install", "-g", CODEX_PACKAGE]
    if prefix:
        cmd.extend(["--prefix", prefix])
    return cmd


def build_install_manual_command() -> str:
    prefix = preferred_npm_prefix()
    if prefix:
        return f"npm install -g {CODEX_PACKAGE} --prefix {prefix}"
    return f"npm install -g {CODEX_PACKAGE}"


def build_codex_subprocess_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """
    为 Codex CLI 构造干净的子进程环境。

    Codex 走 ChatGPT 登录态时，不应继承宿主进程里显式配置的 OpenAI / Azure OpenAI
    鉴权和请求路由环境变量；否则 login status 与 exec 可能出现“检测通过、执行报认证冲突
    或 403”的不一致行为。
    """
    env = dict(base_env or os.environ)
    env["OTEL_SDK_DISABLED"] = "true"
    env.setdefault("CI", "1")
    env.setdefault("TERM", "dumb")
    env.setdefault("NO_COLOR", "1")

    for key in list(env.keys()):
        if key.startswith(CODEX_ENV_DROP_PREFIXES):
            env.pop(key, None)

    return env


def run_command(args: list[str], timeout: int = 30, cwd: str = "") -> CommandResult:
    env = os.environ.copy()
    env.setdefault("OTEL_SDK_DISABLED", "true")
    bin_dir = preferred_bin_dir()
    if bin_dir:
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}" if env.get("PATH") else bin_dir
    return run_command_with_env(args, timeout=timeout, cwd=cwd, env=env)


def detect_cli_version(codex_path: str) -> str:
    if not codex_path:
        return ""
    result = run_command_with_env([codex_path, "--version"], timeout=15, env=build_codex_subprocess_env())
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

    result = run_command_with_env([codex_path, "login", "status"], timeout=20, env=build_codex_subprocess_env())
    output = result.combined_output
    lowered = output.lower()
    if result.returncode != 0:
        return "error", output
    if "logged in" in lowered:
        return "connected", output
    if "not logged" in lowered or "logged out" in lowered:
        return "disconnected", output
    return "unknown", output


def run_command_with_env(
    args: list[str],
    timeout: int = 30,
    cwd: str = "",
    env: dict[str, str] | None = None,
) -> CommandResult:
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
