"""
tests/infra/worker/test_remote_worker_proxy.py

RemoteWorkerProxy 单测：覆盖元信息透出、最近活动时间和错误记录。
"""

from unittest.mock import AsyncMock

import pytest

from server.domain.worker.entity.capability_entity import CapabilityEntity
from server.domain.worker.entity.worker_entity import WorkerMetaEntity
from server.infra.worker.remote_worker_proxy import RemoteWorkerProxy


@pytest.mark.asyncio
async def test_remote_worker_proxy_exposes_metadata_and_enabled_capabilities():
    ws = AsyncMock()
    proxy = RemoteWorkerProxy(
        worker_id="browser-1",
        capabilities=[
            CapabilityEntity(name="browser_open", description="open"),
            CapabilityEntity(name="browser_click", description="click", risk_level="medium"),
        ],
        ws=ws,
        meta=WorkerMetaEntity(
            worker_id="browser-1",
            kind="browser",
            label="Chrome Web Client",
            version="0.1.0",
            platform="macOS-arm64",
            browser_type="chromium",
            headless=True,
            allowed_origins=["https://example.com"],
            max_sessions=2,
            max_screenshot_bytes=65536,
            max_text_chars=2000,
            max_html_chars=8000,
            source="127.0.0.1:50123",
        ),
        enabled_capability_names=["browser_open"],
    )

    info = proxy.to_worker_info()

    assert info.kind == "browser"
    assert info.browser_type == "chromium"
    assert info.allowed_origins == ["https://example.com"]
    assert info.max_sessions == 2
    assert info.source == "127.0.0.1:50123"
    assert info.enabled_capability_names == ["browser_open"]


def test_remote_worker_proxy_records_error_and_last_seen():
    ws = AsyncMock()
    proxy = RemoteWorkerProxy(
        worker_id="browser-1",
        capabilities=[CapabilityEntity(name="browser_open", description="open")],
        ws=ws,
    )

    before = proxy.to_worker_info().last_seen_at
    proxy.mark_seen()
    after = proxy.to_worker_info().last_seen_at
    assert after >= before

    proxy.resolve("missing", None, "boom")
    assert proxy.to_worker_info().last_error == ""
