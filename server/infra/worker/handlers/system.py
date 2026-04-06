"""
infra/worker/handlers/system.py

内置系统级 capability（白名单）：
- list_dir     列出目录内容
- read_file    读取文件文本
- write_file   写入文件文本
- run_command  执行预定义命令（白名单）
"""

import os
import subprocess
from pathlib import Path

from server.infra.worker.registry import capability

# 允许执行的命令前缀白名单（安全边界）
_ALLOWED_COMMANDS = {"ls", "pwd", "echo", "cat", "df", "ps", "uname", "whoami"}


@capability("list_dir", "列出指定目录下的文件和子目录")
async def list_dir(path: str = ".") -> dict:
    p = Path(path).expanduser().resolve()
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


@capability("read_file", "读取文件内容，返回文本字符串")
async def read_file(path: str) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return {"error": f"文件不存在: {path}"}
    if not p.is_file():
        return {"error": f"不是文件: {path}"}
    try:
        content = p.read_text(encoding="utf-8")
        return {"path": str(p), "content": content}
    except Exception as e:
        return {"error": str(e)}


@capability("write_file", "将文本内容写入文件（覆盖）")
async def write_file(path: str, content: str) -> dict:
    p = Path(path).expanduser().resolve()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"success": True, "path": str(p)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@capability("run_command", "执行白名单内的系统命令，返回标准输出")
async def run_command(command: str) -> dict:
    parts = command.strip().split()
    if not parts:
        return {"error": "命令为空"}
    if parts[0] not in _ALLOWED_COMMANDS:
        return {"error": f"命令 '{parts[0]}' 不在白名单中，允许的命令: {sorted(_ALLOWED_COMMANDS)}"}
    try:
        result = subprocess.run(parts, capture_output=True, text=True, timeout=10)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "命令执行超时（10s）"}
    except Exception as e:
        return {"error": str(e)}
