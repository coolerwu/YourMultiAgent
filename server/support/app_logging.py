"""
server/support/app_logging.py

应用级统一日志：
- 初始化唯一的 app.log 文件
- 提供结构化日志事件入口与上下文透传
- 接管 HTTP 请求与 uvicorn 日志
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from fastapi import FastAPI, Request

from server.config import get_data_dir

_APP_LOG_FILE = "app.log"
_RETENTION_DAYS = 3
_PRUNE_INTERVAL_SECONDS = 3600
_LOG_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("app_log_context", default={})
_UVICORN_LOGGER_NAMES = ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi")


def get_app_log_path() -> Path:
    return get_data_dir() / _APP_LOG_FILE


def configure_app_logging(log_path: str | Path | None = None, force: bool = False) -> Path:
    path = Path(log_path).expanduser().resolve() if log_path else get_app_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if force:
        _remove_file_handlers(root)

    existing_file_handler = next((handler for handler in root.handlers if isinstance(handler, ThreeDayFileHandler)), None)
    if existing_file_handler is not None:
        _configure_named_loggers()
        return Path(existing_file_handler.baseFilename)

    for handler in root.handlers:
        if isinstance(handler, ThreeDayFileHandler) and Path(handler.baseFilename) == path:
            _configure_named_loggers()
            return path

    formatter = JsonLineFormatter()
    file_handler = ThreeDayFileHandler(path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    if not any(_is_non_file_stream_handler(handler) for handler in root.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    _configure_named_loggers()
    return path


def install_http_logging_middleware(app: FastAPI) -> None:
    logger = get_logger("server.http")

    @app.middleware("http")
    async def structured_http_logging(request: Request, call_next):
        request_id = request.headers.get("x-request-id", "").strip() or str(uuid.uuid4())
        request.state.request_id = request_id
        started_at = time.perf_counter()
        client_addr = _client_addr(request)
        route_path = request.url.path
        method = request.method.upper()

        token = bind_log_context(request_id=request_id)
        log_event(
            logger,
            event="http_request_start",
            layer="http",
            action="request",
            status="started",
            method=method,
            path=route_path,
            client_addr=client_addr,
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = _duration_ms(started_at)
            log_event(
                logger,
                event="http_request_error",
                layer="http",
                action="request",
                status="error",
                level=logging.ERROR,
                method=method,
                path=route_path,
                client_addr=client_addr,
                duration_ms=duration_ms,
                extra={"error": _truncate_text(str(exc), 1000)},
            )
            reset_log_context(token)
            raise

        response.headers["X-Request-ID"] = request_id
        log_event(
            logger,
            event="http_request_end",
            layer="http",
            action="request",
            status=_status_from_http_code(response.status_code),
            method=method,
            path=route_path,
            client_addr=client_addr,
            status_code=response.status_code,
            duration_ms=_duration_ms(started_at),
        )
        reset_log_context(token)
        return response


def get_logger(name: str) -> logging.Logger:
    configure_app_logging()
    return logging.getLogger(name)


def bind_log_context(**values: Any) -> Token:
    current = dict(_LOG_CONTEXT.get())
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        current[key] = value
    return _LOG_CONTEXT.set(current)


def reset_log_context(token: Token) -> None:
    _LOG_CONTEXT.reset(token)


@contextmanager
def log_context(**values: Any) -> Iterator[None]:
    token = bind_log_context(**values)
    try:
        yield
    finally:
        reset_log_context(token)


def current_log_context() -> dict[str, Any]:
    return dict(_LOG_CONTEXT.get())


def log_event(
    logger: logging.Logger,
    *,
    event: str,
    layer: str,
    action: str,
    status: str = "success",
    level: int = logging.INFO,
    message: str = "",
    extra: dict[str, Any] | None = None,
    **fields: Any,
) -> None:
    payload = {
        "event": event,
        "layer": layer,
        "action": action,
        "status": status,
        **{key: value for key, value in fields.items() if _has_value(value)},
    }
    if extra:
        payload["extra"] = extra
    logger.log(level, message or event, extra={"event_data": payload})


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            **current_log_context(),
        }

        event_data = getattr(record, "event_data", None)
        if isinstance(event_data, dict):
            payload.update(_make_jsonable(event_data))
            if record.msg and record.msg != payload.get("event"):
                payload.setdefault("message", record.getMessage())
        else:
            payload.update(self._build_default_payload(record))

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(_make_jsonable(payload), ensure_ascii=False)

    def _build_default_payload(self, record: logging.LogRecord) -> dict[str, Any]:
        if record.name == "uvicorn.access":
            access_payload = _parse_uvicorn_access(record)
            if access_payload is not None:
                return access_payload

        return {
            "event": "log",
            "layer": _infer_layer(record.name),
            "action": "message",
            "status": "error" if record.levelno >= logging.ERROR else "info",
            "message": record.getMessage(),
        }


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
    log_event(
        logger,
        event="ai_request",
        layer="ai",
        action=phase,
        status="started",
        agent_name=agent_name,
        node_id=node_id,
        provider=provider,
        model=model,
        extra={
            "messages": [_message_preview(item) for item in messages],
            **(extra or {}),
        },
    )


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
    log_event(
        logger,
        event="ai_response",
        layer="ai",
        action=phase,
        status="success",
        agent_name=agent_name,
        node_id=node_id,
        provider=provider,
        model=model,
        extra={
            "response": _response_preview(response),
            **(extra or {}),
        },
    )


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
    log_event(
        logger,
        event="tool_call",
        layer="tool",
        action=tool_name,
        status=status,
        node_id=node_id,
        agent_name=agent_name,
        extra={
            "args": _truncate_text(_safe_json(args or {}), 500) if args is not None else "",
            "result": _truncate_text(_stringify(result), 500) if result is not None else "",
        },
    )


def log_ai_error(
    *,
    logger: logging.Logger,
    phase: str,
    agent_name: str,
    node_id: str,
    error: Exception | str,
    extra: dict[str, Any] | None = None,
) -> None:
    log_event(
        logger,
        event="ai_error",
        layer="ai",
        action=phase,
        status="error",
        level=logging.ERROR,
        agent_name=agent_name,
        node_id=node_id,
        extra={
            "error": _truncate_text(str(error), 1000),
            **(extra or {}),
        },
    )


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


def _parse_uvicorn_access(record: logging.LogRecord) -> dict[str, Any] | None:
    args = record.args
    if not isinstance(args, tuple) or len(args) < 5:
        return None
    client_addr, method, path, http_version, status_code = args[:5]
    return {
        "event": "http_access",
        "layer": "http",
        "action": "access",
        "status": _status_from_http_code(int(status_code)),
        "client_addr": client_addr,
        "method": method,
        "path": path,
        "status_code": int(status_code),
        "http_version": str(http_version),
    }


def _configure_named_loggers() -> None:
    for logger_name in _UVICORN_LOGGER_NAMES:
        logger = logging.getLogger(logger_name)
        logger.handlers = []
        logger.propagate = True
        logger.setLevel(logging.INFO)


def _remove_file_handlers(root: logging.Logger) -> None:
    for handler in list(root.handlers):
        if isinstance(handler, ThreeDayFileHandler):
            root.removeHandler(handler)
            handler.close()


def _is_non_file_stream_handler(handler: logging.Handler) -> bool:
    return isinstance(handler, logging.StreamHandler) and not isinstance(handler, ThreeDayFileHandler)


def _client_addr(request: Request) -> str:
    if request.client is None:
        return ""
    return f"{request.client.host}:{request.client.port}"


def _duration_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _status_from_http_code(status_code: int) -> str:
    if status_code >= 500:
        return "error"
    if status_code >= 400:
        return "client_error"
    if status_code >= 300:
        return "redirect"
    return "success"


def _infer_layer(logger_name: str) -> str:
    parts = logger_name.split(".")
    if logger_name.startswith("uvicorn"):
        return "http"
    if len(parts) >= 2 and parts[0] == "server":
        return parts[1]
    return parts[0] if parts else "app"


def _make_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _make_jsonable(item) for key, item in value.items() if _has_value(item)}
    if isinstance(value, (list, tuple)):
        return [_make_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


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


def _parse_line_timestamp(line: str) -> float | None:
    if not line:
        return None
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        timestamp = payload.get("timestamp")
        if isinstance(timestamp, str):
            return _parse_iso_timestamp(timestamp)

    if len(line) < 19:
        return None
    try:
        dt = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return dt.timestamp()


def _parse_iso_timestamp(value: str) -> float | None:
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return None
