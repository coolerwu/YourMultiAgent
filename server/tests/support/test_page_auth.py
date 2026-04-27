import time

from server.domain.agent.agent_entity import GlobalSettingsEntity, PageAuthConfigEntity
from server.infra.store.workspace_json import save_global_settings
from server.support import page_auth


def test_auth_disabled_without_page_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    settings = page_auth.load_auth_settings()

    assert settings.enabled is False
    assert page_auth.verify_token("") is True


def test_auth_disabled_when_page_auth_flag_is_false(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    save_global_settings(
        tmp_path,
        GlobalSettingsEntity(
            page_auth=PageAuthConfigEntity(
                enabled=False,
                access_key="ak-demo",
                secret_key="sk-demo",
                token_ttl_seconds=60,
            )
        ),
    )

    settings = page_auth.load_auth_settings()

    assert settings.enabled is False
    assert page_auth.verify_token("") is True


def test_login_with_aksk_creates_verifiable_token(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    save_global_settings(
        tmp_path,
        GlobalSettingsEntity(
            page_auth=PageAuthConfigEntity(
                enabled=True,
                access_key="ak-demo",
                secret_key="sk-demo",
                token_ttl_seconds=60,
            )
        ),
    )

    result = page_auth.login_with_aksk("ak-demo", "sk-demo", now=100)

    assert result["enabled"] is True
    assert result["expires_at"] == 160
    assert page_auth.verify_token(result["token"], now=120) is True
    assert page_auth.verify_token(result["token"], now=161) is False


def test_login_rejects_wrong_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    save_global_settings(
        tmp_path,
        GlobalSettingsEntity(
            page_auth=PageAuthConfigEntity(enabled=True, access_key="ak-demo", secret_key="sk-demo")
        ),
    )

    try:
        page_auth.login_with_aksk("ak-demo", "bad", now=int(time.time()))
    except ValueError as exc:
        assert "不正确" in str(exc)
    else:
        raise AssertionError("login should reject bad secret")
