"""
tests/infra/worker/test_worker_router.py

WorkerRouter 单元测试：本机优先路由、远程路由、注册/注销、无 capability 时抛错。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from server.domain.worker.entity.capability_entity import CapabilityEntity
from server.domain.worker.entity.worker_entity import WorkerInfoEntity
from server.infra.worker.worker_router import WorkerRouter


def _make_local_worker(cap_names: list[str]):
    caps = [CapabilityEntity(name=n, description=f"desc {n}") for n in cap_names]
    worker = MagicMock()
    worker.list_capabilities.return_value = caps
    worker.invoke = AsyncMock(return_value="local_result")
    return worker


def _make_proxy(worker_id: str, cap_names: list[str]):
    caps = [CapabilityEntity(name=n, description=f"remote {n}", worker_id=worker_id)
            for n in cap_names]
    proxy = MagicMock()
    proxy.worker_id = worker_id
    proxy.list_capabilities.return_value = caps
    proxy.list_registered_capabilities.return_value = caps
    proxy.invoke = AsyncMock(return_value="remote_result")
    proxy.set_enabled_capabilities.side_effect = lambda _, names: WorkerInfoEntity(
        worker_id=worker_id,
        label=worker_id,
        kind="generic",
        status="online",
        registered_capabilities=caps,
        enabled_capability_names=list(names),
    )
    proxy.to_worker_info.return_value = WorkerInfoEntity(
        worker_id=worker_id,
        label=worker_id,
        kind="generic",
        status="online",
        registered_capabilities=caps,
        enabled_capability_names=cap_names,
    )
    return proxy


@pytest.mark.asyncio
async def test_local_capability_routed_locally():
    local = _make_local_worker(["read_file"])
    router = WorkerRouter(local)
    result = await router.invoke("read_file", {"path": "test.txt"})
    assert result == "local_result"
    local.invoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_remote_capability_routed_to_remote():
    local = _make_local_worker(["read_file"])
    router = WorkerRouter(local)
    proxy = _make_proxy("remote-1", ["code_exec"])
    router.register_remote(proxy)

    result = await router.invoke("code_exec", {"code": "print(1)"})
    assert result == "remote_result"
    proxy.invoke.assert_awaited_once()
    local.invoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_local_wins_over_remote_same_name():
    """同名 capability，本机优先"""
    local = _make_local_worker(["read_file"])
    router = WorkerRouter(local)
    proxy = _make_proxy("remote-1", ["read_file"])
    router.register_remote(proxy)

    await router.invoke("read_file", {})
    local.invoke.assert_awaited_once()
    proxy.invoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_capability_raises():
    local = _make_local_worker([])
    router = WorkerRouter(local)
    with pytest.raises(ValueError, match="没有任何 Worker 支持"):
        await router.invoke("nonexistent", {})


def test_list_capabilities_aggregates():
    local = _make_local_worker(["read_file", "write_file"])
    router = WorkerRouter(local)
    proxy = _make_proxy("remote-1", ["code_exec"])
    router.register_remote(proxy)

    caps = router.list_capabilities()
    names = {c.name for c in caps}
    assert names == {"read_file", "write_file", "code_exec"}


def test_unregister_remote():
    local = _make_local_worker([])
    router = WorkerRouter(local)
    proxy = _make_proxy("remote-1", ["code_exec"])
    router.register_remote(proxy)
    assert "remote-1" in router.list_remote_workers()

    router.unregister_remote("remote-1")
    assert "remote-1" not in router.list_remote_workers()


def test_set_enabled_capabilities_filters_remote_capabilities(tmp_path):
    local = _make_local_worker(["read_file"])
    router = WorkerRouter(local, tmp_path)
    proxy = _make_proxy("browser-1", ["browser_open", "browser_click"])
    router.register_remote(proxy)

    router.set_enabled_capabilities("browser-1", ["browser_open"])

    proxy.set_enabled_capabilities.assert_called_once_with("browser-1", ["browser_open"])


def test_remote_enabled_config_persists_across_router_restart(tmp_path):
    local = _make_local_worker([])
    router = WorkerRouter(local, tmp_path)
    proxy = _make_proxy("browser-1", ["browser_open", "browser_click"])
    router.register_remote(proxy)
    router.set_enabled_capabilities("browser-1", ["browser_open"])

    router2 = WorkerRouter(local, tmp_path)
    proxy2 = _make_proxy("browser-1", ["browser_open", "browser_click"])
    router2.register_remote(proxy2)

    proxy2.set_enabled_capabilities.assert_called_once_with("browser-1", ["browser_open"])
