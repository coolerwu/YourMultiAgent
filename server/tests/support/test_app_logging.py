from types import SimpleNamespace

from server.support.app_logging import _message_preview, _response_preview


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
