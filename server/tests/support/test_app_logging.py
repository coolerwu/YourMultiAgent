import json
import logging
from types import SimpleNamespace

from server.support.app_logging import (
    _message_preview,
    _response_preview,
    bind_log_context,
    configure_app_logging,
    get_logger,
    log_event,
    reset_log_context,
)


def test_message_preview_truncates_and_keeps_tool_calls():
    message = SimpleNamespace(
        content="hello " * 200,
        tool_calls=[{"id": "tool-1", "name": "read_file", "args": {"path": "/tmp/demo.txt"}}],
    )

    preview = _message_preview(message)

    assert preview["type"] == "SimpleNamespace"
    assert preview["content"].endswith("...")
    assert preview["tool_calls"][0]["name"] == "read_file"


def test_response_preview_handles_plain_text():
    response = SimpleNamespace(content="done", tool_calls=[])

    preview = _response_preview(response)

    assert preview["type"] == "SimpleNamespace"
    assert preview["content"] == "done"
    assert preview["tool_calls"] == []


def test_log_event_writes_structured_json_line(tmp_path):
    log_path = tmp_path / "app.log"
    configure_app_logging(log_path=log_path, force=True)
    logger = get_logger("tests.app_logging")

    token = bind_log_context(request_id="req-1", workspace_id="ws-1")
    try:
        log_event(
            logger,
            event="workspace_saved",
            layer="store",
            action="save_workspace",
            status="success",
            session_id="session-1",
            extra={"path": "/tmp/workspace.json"},
        )
    finally:
        reset_log_context(token)

    payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["event"] == "workspace_saved"
    assert payload["layer"] == "store"
    assert payload["action"] == "save_workspace"
    assert payload["status"] == "success"
    assert payload["request_id"] == "req-1"
    assert payload["workspace_id"] == "ws-1"
    assert payload["session_id"] == "session-1"
    assert payload["extra"]["path"] == "/tmp/workspace.json"


def test_configure_app_logging_reuses_existing_file_handler(tmp_path):
    log_path = tmp_path / "app.log"
    first = configure_app_logging(log_path=log_path, force=True)
    second = configure_app_logging(log_path=log_path)

    assert first == log_path
    assert second == log_path
    assert first == second


def test_uvicorn_access_logger_is_written_as_structured_http_access(tmp_path):
    log_path = tmp_path / "app.log"
    configure_app_logging(log_path=log_path, force=True)

    logging.getLogger("uvicorn.access").info(
        '%s - "%s %s HTTP/%s" %s',
        "127.0.0.1:51234",
        "GET",
        "/api/health",
        "1.1",
        200,
    )

    payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["event"] == "http_access"
    assert payload["layer"] == "http"
    assert payload["action"] == "access"
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/health"
    assert payload["status_code"] == 200
    assert payload["client_addr"] == "127.0.0.1:51234"
