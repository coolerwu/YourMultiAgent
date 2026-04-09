"""
tests/infra/worker/test_local_worker.py

LocalWorker 单测：覆盖 capability 枚举与 invoke 委托。
"""

from unittest.mock import AsyncMock

import pytest

from server.domain.worker.capability_entity import CapabilityEntity
from server.infra.worker.local_worker import LocalWorker


def test_local_worker_lists_local_capabilities(monkeypatch):
    capabilities = [CapabilityEntity(name="read_file", description="read")]
    monkeypatch.setattr("server.infra.worker.local_worker.registry.get_all_capabilities", lambda: capabilities)

    worker = LocalWorker()
    items = worker.list_capabilities()

    assert items == capabilities
    assert worker.list_workers()[0].enabled_capability_names == ["read_file"]


@pytest.mark.asyncio
async def test_local_worker_invokes_registry(monkeypatch):
    invoke = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr("server.infra.worker.local_worker.registry.invoke", invoke)

    worker = LocalWorker()
    result = await worker.invoke("read_file", {"path": "a.txt"}, {"work_dir": "/tmp/demo"})

    assert result == {"ok": True}
    invoke.assert_awaited_once_with("read_file", {"path": "a.txt"}, {"work_dir": "/tmp/demo"})
