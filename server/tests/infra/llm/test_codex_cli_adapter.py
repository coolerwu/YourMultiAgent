import os

from server.infra.llm.codex_cli_adapter import _build_codex_env


def test_build_codex_env_removes_empty_openai_auth_vars(monkeypatch):
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


def test_build_codex_env_keeps_non_empty_auth_vars(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_AUTH_TOKEN", "token")

    env = _build_codex_env()

    assert env["OPENAI_API_KEY"] == "sk-test"
    assert env["OPENAI_AUTH_TOKEN"] == "token"
