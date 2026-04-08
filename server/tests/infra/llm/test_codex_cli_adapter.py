from server.infra.llm.codex_cli_adapter import _build_codex_env, _format_codex_error


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
