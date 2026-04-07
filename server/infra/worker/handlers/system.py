"""
infra/worker/handlers/system.py

内置系统级 capability（白名单）：
- list_dir     列出目录内容
- read_file    读取文件文本（支持跨 Agent 相对路径）
- write_file   写入文件文本（允许写入 agent work_dir 或 workspace_root/shared）
- run_command  执行白名单命令（CWD = agent work_dir）

_context 参数由 registry.invoke 注入，包含 {"work_dir": "...", "workspace_root": "..."}。
"""

import os
import subprocess
from pathlib import Path
from typing import Any

from server.infra.worker.registry import capability

_ALLOWED_COMMANDS = {"ls", "pwd", "echo", "cat", "df", "ps", "uname", "whoami", "find", "tree"}


def _workspace_shared_dir(context: dict[str, Any]) -> Path:
    workspace_root = context.get("workspace_root") or context.get("work_dir", ".")
    return (Path(workspace_root).expanduser().resolve() / "shared").resolve()


def _resolve_path(path: str, work_dir: str, allow_cross_read: bool = True, shared_dir: Path | None = None) -> Path:
    """
    解析路径：
    - 相对路径 → 相对于 work_dir 解析
    - shared/... → 优先相对于 workspace_root/shared 解析
    - 绝对路径 → 直接使用
    - allow_cross_read=False 时，确保结果在 work_dir 内
    """
    base = Path(work_dir).expanduser().resolve()
    p = Path(path)
    if not p.is_absolute() and shared_dir is not None and p.parts and p.parts[0] == "shared":
        p = (shared_dir / Path(*p.parts[1:])).resolve()
    elif not p.is_absolute():
        p = (base / path).resolve()
    else:
        p = p.resolve()
    if not allow_cross_read:
        allowed_bases = [base]
        if shared_dir is not None:
            allowed_bases.append(shared_dir)
        for allowed_base in allowed_bases:
            try:
                p.relative_to(allowed_base)
                break
            except ValueError:
                continue
        else:
            raise PermissionError(
                f"写操作只允许写入当前 work_dir 或 workspace/shared: {base}"
            )
    return p


def _get_work_dir(context: dict[str, Any]) -> str:
    return context.get("work_dir", ".")


@capability("list_dir", "列出指定目录下的文件和子目录")
async def list_dir(path: str = ".", _context: dict = None) -> dict:
    context = _context or {}
    work_dir = _get_work_dir(context)
    p = _resolve_path(path, work_dir, shared_dir=_workspace_shared_dir(context))
    if not p.exists():
        return {"error": f"路径不存在: {path}"}
    entries = []
    for entry in p.iterdir():
        entries.append({
            "name": entry.name,
            "is_dir": entry.is_dir(),
            "size": entry.stat().st_size if entry.is_file() else None,
        })
    return {"path": str(p), "entries": sorted(entries, key=lambda e: e["name"])}


@capability("read_file", "读取文件内容（可用 ../agentB/file.txt 跨读其他 Agent 目录）")
async def read_file(path: str, _context: dict = None) -> dict:
    context = _context or {}
    work_dir = _get_work_dir(context)
    p = _resolve_path(path, work_dir, allow_cross_read=True, shared_dir=_workspace_shared_dir(context))
    if not p.exists():
        return {"error": f"文件不存在: {p}"}
    if not p.is_file():
        return {"error": f"不是文件: {p}"}
    try:
        return {"path": str(p), "content": p.read_text(encoding="utf-8")}
    except Exception as e:
        return {"error": str(e)}


@capability("write_file", "写入文件内容（只能写入当前 Agent 的工作目录）")
async def write_file(path: str, content: str, _context: dict = None) -> dict:
    context = _context or {}
    work_dir = _get_work_dir(context)
    try:
        p = _resolve_path(
            path,
            work_dir,
            allow_cross_read=False,
            shared_dir=_workspace_shared_dir(context),
        )
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"success": True, "path": str(p)}
    except PermissionError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@capability("run_command", "执行白名单内的系统命令（在 Agent 工作目录中运行）")
async def run_command(command: str, _context: dict = None) -> dict:
    work_dir = _get_work_dir(_context or {})
    parts = command.strip().split()
    if not parts:
        return {"error": "命令为空"}
    if parts[0] not in _ALLOWED_COMMANDS:
        return {"error": f"命令 '{parts[0]}' 不在白名单中，允许: {sorted(_ALLOWED_COMMANDS)}"}
    cwd = str(Path(work_dir).expanduser().resolve())
    try:
        result = subprocess.run(parts, capture_output=True, text=True, timeout=10, cwd=cwd)
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        return {"error": "命令执行超时（10s）"}
    except Exception as e:
        return {"error": str(e)}
