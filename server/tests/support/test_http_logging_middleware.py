import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.support.app_logging import configure_app_logging, install_http_logging_middleware


def test_http_logging_middleware_records_request_lifecycle(tmp_path):
    log_path = tmp_path / "app.log"
    configure_app_logging(log_path=log_path, force=True)

    app = FastAPI()
    install_http_logging_middleware(app)

    @app.get("/ok")
    async def ok():
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/ok", headers={"x-request-id": "req-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-123"

    payloads = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    start = next(item for item in payloads if item["event"] == "http_request_start")
    end = next(item for item in payloads if item["event"] == "http_request_end")

    assert start["request_id"] == "req-123"
    assert start["path"] == "/ok"
    assert start["method"] == "GET"
    assert end["request_id"] == "req-123"
    assert end["status_code"] == 200
    assert end["status"] == "success"
    assert end["duration_ms"] >= 0


def test_http_logging_middleware_records_exceptions(tmp_path):
    log_path = tmp_path / "app.log"
    configure_app_logging(log_path=log_path, force=True)

    app = FastAPI()
    install_http_logging_middleware(app)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500

    payloads = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    error = next(item for item in payloads if item["event"] == "http_request_error")

    assert error["path"] == "/boom"
    assert error["method"] == "GET"
    assert error["status"] == "error"
    assert error["extra"]["error"] == "boom"
