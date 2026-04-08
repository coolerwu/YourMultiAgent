"""
server/support/app_logging.py

应用级统一日志：
- 初始化唯一的 app.log 文件
- 记录 AI 请求、响应、工具调用和异常
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
import time
from typing import Any

from server.config import get_data_dir

_APP_LOG_FILE = "app.log"
_RETENTION_DAYS = 3
_PRUNE_INTERVAL_SECONDS = 3600


def get_app_log_path() -> Path:
    return get_data_dir() / _APP_LOG_FILE


def configure_app_logging() -> Path:
    log_path = get_app_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    for handler in root.handlers:
        if isinstance(handler, ThreeDayFileHandler) and Path(handler.baseFilename) == log_path:
            return log_path

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = ThreeDayFileHandler(
        log_path,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    if not any(isinstance(handler, logging.StreamHandler) and not isinstance(handler, ThreeDayFileHandler) for handler in root.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    return log_path


def get_logger(name: str) -> logging.Logger:
    configure_app_logging()
    return logging.getLogger(name)


class ThreeDayFileHandler(logging.FileHandler):
    def __init__(self, filename: str | Path, encoding: str | None = None) -> None:
        super().__init__(filename, encoding=encoding)
        self._last_prune_at = 0.0
        self._prune_old_lines()

    def emit(self, record: logging.LogRecord) -> None:
        now = time.time()
        if now - self._last_prune_at >= _PRUNE_INTERVAL_SECONDS:
            self._prune_old_lines()
            self._last_prune_at = now
        super().emit(record)

    def _prune_old_lines(self) -> None:
        path = Path(self.baseFilename)
        if not path.exists():
            return
        cutoff = time.time() - _RETENTION_DAYS * 24 * 60 * 60
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if not lines:
            return

        kept_lines: list[str] = []
        keep_current_block = True
        for line in lines:
            timestamp = _parse_line_timestamp(line)
            if timestamp is not None:
                keep_current_block = timestamp >= cutoff
            if keep_current_block:
                kept_lines.append(line)

        new_content = "\n".join(kept_lines)
        if kept_lines:
            new_content += "\n"
        path.write_text(new_content, encoding="utf-8")


def log_ai_request(
    *,
    logger: logging.Logger,
    phase: str,
    agent_name: str,
    node_id: str,
    provider: str,
    model: str,
    messages: list[Any],
    extra: dict[str, Any] | None = None,
) -> None:
    payload = {
        "event": "ai_request",
        "phase": phase,
        "agent_name": agent_name,
        "node_id": node_id,
        "provider": provider,
        "model": model,
        "messages": [_message_preview(item) for item in messages],
        "extra": extra or {},
    }
    logger.info(_json(payload))


def log_ai_response(
    *,
    logger: logging.Logger,
    phase: str,
    agent_name: str,
    node_id: str,
    provider: str,
    model: str,
    response: Any,
    extra: dict[str, Any] | None = None,
) -> None:
    payload = {
        "event": "ai_response",
        "phase": phase,
        "agent_name": agent_name,
        "node_id": node_id,
        "provider": provider,
        "model": model,
        "response": _response_preview(response),
        "extra": extra or {},
    }
    logger.info(_json(payload))


def log_tool_event(
    *,
    logger: logging.Logger,
    node_id: str,
    agent_name: str,
    tool_name: str,
    status: str,
    args: dict[str, Any] | None = None,
    result: Any = None,
) -> None:
    payload = {
        "event": "tool_call",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "node_id": node_id,
        "agent_name": agent_name,
        "tool_name": tool_name,
        "status": status,
        "args": _truncate_text(_safe_json(args or {}), 500) if args is not None else "",
        "result": _truncate_text(_stringify(result), 500) if result is not None else "",
    }
    logger.info(_json(payload))


def log_ai_error(
    *,
    logger: logging.Logger,
    phase: str,
    agent_name: str,
    node_id: str,
    error: Exception | str,
    extra: dict[str, Any] | None = None,
) -> None:
    payload = {
        "event": "ai_error",
        "phase": phase,
        "agent_name": agent_name,
        "node_id": node_id,
        "error": _truncate_text(str(error), 1000),
        "extra": extra or {},
    }
    logger.exception(_json(payload))


def _message_preview(message: Any) -> dict[str, Any]:
    tool_calls = getattr(message, "tool_calls", None) or []
    return {
        "type": message.__class__.__name__,
        "content": _truncate_text(_stringify(getattr(message, "content", "")), 500),
        "tool_calls": [
            {
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "args": _truncate_text(_safe_json(item.get("args", {})), 300),
            }
            for item in tool_calls
        ],
    }


def _response_preview(response: Any) -> dict[str, Any]:
    tool_calls = getattr(response, "tool_calls", None) or []
    return {
        "type": response.__class__.__name__,
        "content": _truncate_text(_stringify(getattr(response, "content", "")), 1000),
        "tool_calls": [
            {
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "args": _truncate_text(_safe_json(item.get("args", {})), 300),
            }
            for item in tool_calls
        ],
    }


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_stringify(item) for item in value)
    return str(value)


def _truncate_text(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _parse_line_timestamp(line: str) -> float | None:
    if len(line) < 19:
        return None
    try:
        dt = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return dt.timestamp()
