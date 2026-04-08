import asyncio
import json
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage

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
    assert "OPENAI_API_KEY" not in env
    assert "OPENAI_AUTH_TOKEN" not in env
    assert "OPENAI_BASE_URL" not in env
    assert "OPENAI_PROJECT" not in env


def test_codex_adapter_disables_simple_mode_when_binding_tools():
    adapter = CodexCLIAdapter(model="", codex_path="codex", simple_output_mode=True)
    bound = adapter.bind_tools([{"name": "read_file"}])

    assert bound._simple_output_mode is False


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
    def __init__(self, output_path: Path, payload: dict | None = None) -> None:
        self.returncode = 0
        self._output_path = output_path
        self._payload = payload or {"content": "ok"}

    async def communicate(self):
        self._output_path.write_text(json.dumps(self._payload, ensure_ascii=False), encoding="utf-8")
        return b"", b""

    def kill(self) -> None:  # pragma: no cover - success path should not kill
        self.returncode = -9

    async def wait(self):  # pragma: no cover - success path should not wait
        return self.returncode


class _RawProcess:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout.encode("utf-8"), self._stderr.encode("utf-8")

    def kill(self) -> None:  # pragma: no cover - no kill on success
        self.returncode = -9

    async def wait(self):  # pragma: no cover - no wait on success
        return self.returncode


@pytest.mark.asyncio
async def test_codex_adapter_timeout_kills_subprocess(monkeypatch):
    process = _BlockingProcess()

    async def _fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(codex_cli_adapter.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    monkeypatch.setattr(codex_cli_adapter, "_CODEX_EXEC_TIMEOUT_SECONDS", 0.01)
    adapter = CodexCLIAdapter(model="", codex_path="codex")

    with pytest.raises(ValueError, match="Codex CLI 执行超时"):
        await adapter.ainvoke([HumanMessage(content="hello")])

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

    async def _fake_create_subprocess_exec(*args, **_kwargs):
        calls["count"] += 1
        output_path = Path(args[args.index("-o") + 1])
        if calls["count"] == 1:
            return first
        return _SuccessProcess(output_path, payload={"content": "第二次成功"})

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

    async def _fake_create_subprocess_exec(*args, **_kwargs):
        captured["args"] = list(args)
        return _RawProcess(
            "OpenAI Codex v0.118.0\n--------\nuser\nhello\ncodex\n你好\ntokens used\n123\n"
        )

    monkeypatch.setattr(codex_cli_adapter.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    adapter = CodexCLIAdapter(model="", codex_path="codex", simple_output_mode=True)

    result = await adapter.ainvoke([HumanMessage(content="hello")])

    assert result.content == "你好"
    assert "--output-schema" not in captured["args"]
    assert "-o" not in captured["args"]
