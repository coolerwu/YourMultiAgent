from fastapi.testclient import TestClient

from server.domain.agent.agent_entity import GlobalSettingsEntity, PageAuthConfigEntity
from server.infra.store.workspace_json import save_global_settings
from server.main import app


def test_auth_status_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    with TestClient(app) as client:
        response = client.get("/api/auth/status")

    assert response.status_code == 200
    assert response.json() == {"enabled": False}


def test_auth_login_and_api_middleware(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    save_global_settings(
        tmp_path,
        GlobalSettingsEntity(
            page_auth=PageAuthConfigEntity(enabled=True, access_key="ak-demo", secret_key="sk-demo")
        ),
    )

    with TestClient(app) as client:
        unauthorized = client.get("/api/settings/providers")
        login = client.post("/api/auth/login", json={"access_key": "ak-demo", "secret_key": "sk-demo"})
        token = login.json()["token"]
        authorized = client.get("/api/settings/providers", headers={"Authorization": f"Bearer {token}"})

    assert unauthorized.status_code == 401
    assert login.status_code == 200
    assert token
    assert authorized.status_code == 200


def test_auth_login_rejects_bad_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    save_global_settings(
        tmp_path,
        GlobalSettingsEntity(
            page_auth=PageAuthConfigEntity(enabled=True, access_key="ak-demo", secret_key="sk-demo")
        ),
    )

    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={"access_key": "ak-demo", "secret_key": "bad"})

    assert response.status_code == 401
