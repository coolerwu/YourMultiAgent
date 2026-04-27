import asyncio
import json
import pytest
from langchain_core.messages import AIMessageChunk, HumanMessage

import server.infra.llm.codex_cli_adapter as codex_cli_adapter
from server.infra.llm.codex_cli_adapter import CodexCLIAdapter, _build_codex_env, _format_codex_error


def test_build_codex_env_removes_openai_auth_vars_even_when_empty(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_AUTH_TOKEN", "   ")
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    monkeypatch.setenv("OPENAI_PROJECT", "")
    monkeypatch.setenv("HOME", "/home/qiuqiu")

    env = _build_codex_env()

    assert env["HOME"] == "/home/qiuqiu"
    assert env["OTEL_SDK_DISABLED"] == "true"
    assert env["CI"] == "1"
    assert env["TERM"] == "dumb"
    assert env["NO_COLOR"] == "1"
    assert "OPENAI_API_KEY" not in env
    assert "OPENAI_AUTH_TOKEN" not in env
    assert "OPENAI_BASE_URL" not in env
    assert "OPENAI_PROJECT" not in env


def test_codex_adapter_disables_simple_mode_when_binding_tools():
    adapter = CodexCLIAdapter(model="", codex_path="codex", simple_output_mode=True)
    bound = adapter.bind_tools([{"name": "read_file"}])

    assert bound._simple_output_mode is False


@pytest.mark.asyncio
async def test_codex_adapter_astream_streams_simple_mode_deltas(monkeypatch):
    adapter = CodexCLIAdapter(model="", codex_path="codex", simple_output_mode=True)

    async def _fake_stream(_args, _work_dir):
        yield "O"
        yield "K"

    monkeypatch.setattr(codex_cli_adapter, "_stream_codex_text_with_retry", _fake_stream)

    chunks = [chunk async for chunk in adapter.astream([HumanMessage(content="hello")])]

    assert len(chunks) == 2
    assert isinstance(chunks[0], AIMessageChunk)
    assert isinstance(chunks[0], AIMessageChunk)
    assert chunks[0].content == "O"
    assert chunks[0].chunk_position is None
    assert chunks[1].content == "K"
    assert chunks[1].chunk_position == "last"


@pytest.mark.asyncio
async def test_codex_adapter_astream_yields_single_final_chunk_for_structured_output(monkeypatch):
    adapter = CodexCLIAdapter(model="", codex_path="codex", simple_output_mode=False)

    async def _fake_run(_messages):
        return codex_cli_adapter.AIMessage(content="OK", tool_calls=[])

    monkeypatch.setattr(adapter, "_run", _fake_run)

    chunks = [chunk async for chunk in adapter.astream([HumanMessage(content="hello")])]

    assert len(chunks) == 1
    assert isinstance(chunks[0], AIMessageChunk)
    assert chunks[0].content == "OK"
    assert chunks[0].chunk_position == "last"


def test_codex_adapter_build_exec_args_uses_configured_sandbox(monkeypatch):
    monkeypatch.setattr(codex_cli_adapter, "_CODEX_SANDBOX_MODE", "workspace-write")
    adapter = CodexCLIAdapter(model="", codex_path="codex")

    args = adapter._build_exec_args("hello")

    assert "--sandbox" in args
    sandbox_index = args.index("--sandbox")
    assert args[sandbox_index + 1] == "workspace-write"


def test_build_codex_env_removes_openai_auth_vars_even_when_non_empty(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_AUTH_TOKEN", "token")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("OPENAI_PROJECT", "proj_test")

    env = _build_codex_env()

    assert "OPENAI_API_KEY" not in env
    assert "OPENAI_AUTH_TOKEN" not in env
    assert "OPENAI_BASE_URL" not in env
    assert "OPENAI_PROJECT" not in env


def test_build_codex_env_removes_openai_prefix_vars(monkeypatch):
    monkeypatch.setenv("OPENAI_DEFAULT_HEADERS", '{"Authorization":"Bearer bad"}')
    monkeypatch.setenv("OPENAI_API_TYPE", "azure")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://azure.example.com")
    monkeypatch.setenv("HOME", "/home/qiuqiu")

    env = _build_codex_env()

    assert env["HOME"] == "/home/qiuqiu"
    assert "OPENAI_DEFAULT_HEADERS" not in env
    assert "OPENAI_API_TYPE" not in env
    assert "AZURE_OPENAI_API_KEY" not in env
    assert "AZURE_OPENAI_ENDPOINT" not in env


def test_build_codex_env_removes_otel_exporter_vars(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otel.example.com")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "Authorization=Bearer bad")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "yourmultiagent")
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "service.name=yourmultiagent")
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")

    env = _build_codex_env()

    assert "OTEL_EXPORTER_OTLP_ENDPOINT" not in env
    assert "OTEL_EXPORTER_OTLP_HEADERS" not in env
    assert "OTEL_SERVICE_NAME" not in env
    assert "OTEL_RESOURCE_ATTRIBUTES" not in env
    assert "OTEL_TRACES_EXPORTER" not in env


def test_format_codex_error_explains_auth_conflict():
    message = _format_codex_error(
        "",
        "Could not resolve authentication method. Expected either api_key or auth_token to be set.",
    )

    assert "混入了额外的 OpenAI 鉴权配置" in message


def test_format_codex_error_explains_forbidden_request():
    message = _format_codex_error(
        "",
        "Error code: 403 - {'error': {'type': 'forbidden', 'message': 'Request not allowed'}}",
    )

    assert "403 Request not allowed" in message


def test_format_codex_error_explains_sandbox_denial():
    message = _format_codex_error(
        "",
        "bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted",
    )

    assert "宿主机不允许 Codex 的 read-only sandbox" in message


def test_format_codex_error_explains_websocket_permission_denial():
    message = _format_codex_error(
        "",
        "failed to connect to websocket: IO error: Operation not permitted (os error 1), "
        "url: wss://chatgpt.com/backend-api/codex/responses",
    )

    assert "禁止 Codex 访问 ChatGPT Codex 实时响应通道" in message


def test_format_codex_error_explains_otel_exporter_failure():
    message = _format_codex_error(
        "",
        "Could not create otel exporter: panicked during initialization",
    )

    assert "初始化 OTEL 导出器失败" in message


class _BlockingProcess:
    def __init__(self) -> None:
        self.returncode = None
        self.killed = False
        self.wait_called = False

    async def communicate(self):
        await asyncio.sleep(3600)
        return b"", b""

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def wait(self):
        self.wait_called = True
        return self.returncode


class _SuccessProcess:
    def __init__(self, payload: dict | None = None) -> None:
        self.returncode = 0
        self._payload = payload or {"content": "ok"}

    async def communicate(self):
        jsonl = (
            '{"type":"thread.started","thread_id":"thread-1"}\n'
            '{"type":"turn.started"}\n'
            f'{{"type":"item.completed","item":{{"id":"item_1","type":"agent_message","text":{self._quoted_payload()}}}}}\n'
            '{"type":"turn.completed"}\n'
        )
        return jsonl.encode("utf-8"), b""

    def kill(self) -> None:  # pragma: no cover - success path should not kill
        self.returncode = -9

    async def wait(self):  # pragma: no cover - success path should not wait
        return self.returncode

    def _quoted_payload(self) -> str:
        return json.dumps(json.dumps(self._payload, ensure_ascii=False), ensure_ascii=False)


class _RawProcess:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self, input=None):  # noqa: A002
        return self._stdout.encode("utf-8"), self._stderr.encode("utf-8")

    def kill(self) -> None:  # pragma: no cover - no kill on success
        self.returncode = -9

    async def wait(self):  # pragma: no cover - no wait on success
        return self.returncode


class _LineReader:
    def __init__(self, lines: list[str]) -> None:
        self._lines = [line.encode("utf-8") for line in lines]

    async def readline(self) -> bytes:
        await asyncio.sleep(0)
        if not self._lines:
            return b""
        return self._lines.pop(0)


class _StreamingProcess:
    def __init__(self, lines: list[str], returncode: int = 0) -> None:
        self.returncode = None
        self._target_returncode = returncode
        self.stdout = _LineReader(lines)
        self.killed = False
        self.wait_called = False
        self.pid = 12345

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def wait(self):
        self.wait_called = True
        if self.returncode is None:
            self.returncode = self._target_returncode
        return self.returncode


@pytest.mark.asyncio
async def test_codex_adapter_timeout_kills_subprocess(monkeypatch):
    process = _BlockingProcess()

    async def _fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(codex_cli_adapter.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    monkeypatch.setattr(codex_cli_adapter, "_CODEX_EXEC_TIMEOUT_SECONDS", 0.01)
    adapter = CodexCLIAdapter(model="", codex_path="codex")

    with pytest.raises(ValueError, match="Codex CLI 执行超时") as exc_info:
        await adapter.ainvoke([HumanMessage(content="hello")])

    assert "codex exec 进程卡住" in str(exc_info.value)

    assert process.killed is True
    assert process.wait_called is True


@pytest.mark.asyncio
async def test_codex_adapter_cancel_kills_subprocess(monkeypatch):
    process = _BlockingProcess()

    async def _fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(codex_cli_adapter.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    monkeypatch.setattr(codex_cli_adapter, "_CODEX_EXEC_TIMEOUT_SECONDS", 100)
    adapter = CodexCLIAdapter(model="", codex_path="codex")

    task = asyncio.create_task(adapter.ainvoke([HumanMessage(content="hello")]))
    await asyncio.sleep(0.01)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert process.killed is True
    assert process.wait_called is True


@pytest.mark.asyncio
async def test_codex_adapter_retries_once_then_succeeds(monkeypatch):
    first = _BlockingProcess()
    calls = {"count": 0}

    async def _fake_create_subprocess_exec(*command_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return first
        return _SuccessProcess(payload={"content": "第二次成功", "tool_calls": []})

    monkeypatch.setattr(codex_cli_adapter.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    monkeypatch.setattr(codex_cli_adapter, "_CODEX_EXEC_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(codex_cli_adapter, "_CODEX_EXEC_MAX_ATTEMPTS", 2)
    adapter = CodexCLIAdapter(model="", codex_path="codex")

    result = await adapter.ainvoke([HumanMessage(content="hello")])

    assert calls["count"] == 2
    assert first.killed is True
    assert result.content == "第二次成功"


@pytest.mark.asyncio
async def test_codex_adapter_simple_mode_reads_stdout_without_schema(monkeypatch):
    captured = {}

    # 模拟 --json 模式的 JSONL 输出
    jsonl_output = (
        '{"type":"message","role":"assistant","content":"你好呀"}\n'
        '{"type":"done"}\n'
    )

    async def _fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = list(args)
        captured["kwargs"] = kwargs
        return _RawProcess(jsonl_output)

    monkeypatch.setattr(codex_cli_adapter.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    adapter = CodexCLIAdapter(model="", codex_path="codex", simple_output_mode=True)

    result = await adapter.ainvoke([HumanMessage(content="hello")])

    assert result.content == "你好呀"
    assert captured["args"][0] == "codex"
    assert "exec" in captured["args"]
    assert "--json" in captured["args"]
    assert any("[human]" in arg for arg in captured["args"])
    assert captured["kwargs"]["stdin"] == codex_cli_adapter.asyncio.subprocess.DEVNULL
    # stderr 应该被重定向到 DEVNULL 避免管道阻塞
    assert captured["kwargs"]["stderr"] == codex_cli_adapter.asyncio.subprocess.DEVNULL


@pytest.mark.asyncio
async def test_codex_adapter_parses_actual_codex_jsonl_event(monkeypatch):
    jsonl_output = (
        '{"type":"thread.started","thread_id":"019d6dc0-e939-75d3-937b-ae0e9c870dad"}\n'
        '{"type":"turn.started"}\n'
        '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"先给一条中间说明"}}\n'
        '{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"最终回答正文"}}\n'
        '{"type":"turn.completed"}\n'
    )

    async def _fake_create_subprocess_exec(*_args, **_kwargs):
        return _RawProcess(jsonl_output)

    monkeypatch.setattr(codex_cli_adapter.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    adapter = CodexCLIAdapter(model="", codex_path="codex", simple_output_mode=True)

    result = await adapter.ainvoke([HumanMessage(content="hello")])

    assert result.content == "最终回答正文"


@pytest.mark.asyncio
async def test_codex_adapter_ignores_non_json_prefix_before_jsonl_events(monkeypatch):
    jsonl_output = (
        'Reading additional input from stdin...\n'
        '{"type":"thread.started","thread_id":"019d6dc0-e939-75d3-937b-ae0e9c870dad"}\n'
        '{"type":"turn.started"}\n'
        '{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"最终回答正文"}}\n'
        '{"type":"turn.completed"}\n'
    )

    async def _fake_create_subprocess_exec(*_args, **_kwargs):
        return _RawProcess(jsonl_output)

    monkeypatch.setattr(codex_cli_adapter.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    adapter = CodexCLIAdapter(model="", codex_path="codex", simple_output_mode=True)

    result = await adapter.ainvoke([HumanMessage(content="hello")])

    assert result.content == "最终回答正文"


@pytest.mark.asyncio
async def test_stream_codex_text_with_retry_yields_message_deltas(monkeypatch):
    captured = {}
    process = _StreamingProcess(
        [
            '{"type":"thread.started","thread_id":"thread-1"}\n',
            '{"type":"turn.started"}\n',
            '{"type":"agent_message_delta","delta":"你"}\n',
            '{"type":"agent_message_content_delta","delta":"好"}\n',
            '{"type":"turn.completed"}\n',
        ]
    )

    async def _fake_create_subprocess_exec(*args, **kwargs):
        captured["kwargs"] = kwargs
        return process

    monkeypatch.setattr(codex_cli_adapter.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    deltas = [delta async for delta in codex_cli_adapter._stream_codex_text_with_retry(["codex", "exec"], "")]

    assert deltas == ["你", "好"]
    assert process.wait_called is True
    # 流式模式下 stdout/stderr 共用 PTY，避免非 TTY 环境下输出缓冲。
    assert captured["kwargs"]["stderr"] == captured["kwargs"]["stdout"]


@pytest.mark.asyncio
async def test_stream_codex_text_with_retry_falls_back_to_completed_message(monkeypatch):
    process = _StreamingProcess(
        [
            '{"type":"thread.started","thread_id":"thread-1"}\n',
            '{"type":"turn.started"}\n',
            '{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"最终回答"}}\n',
            '{"type":"turn.completed"}\n',
        ]
    )

    async def _fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(codex_cli_adapter.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    deltas = [delta async for delta in codex_cli_adapter._stream_codex_text_with_retry(["codex", "exec"], "")]

    assert deltas == ["最终回答"]
    assert process.wait_called is True


def test_extract_assistant_text_strips_plaintext_noise_when_no_json_events():
    text = codex_cli_adapter._extract_assistant_text(
        "Reading additional input from stdin...\n\n最终回答正文\n"
    )

    assert text == "最终回答正文"
