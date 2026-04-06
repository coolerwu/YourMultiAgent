"""
tests/infra/worker/test_registry.py

@capability 装饰器与 registry 调用单测。
"""

import pytest
from server.infra.worker.registry import _REGISTRY, capability, get_all_capabilities, invoke


@pytest.fixture(autouse=True)
def clean_registry():
    """每个 test 前后清空注册表，避免污染"""
    _REGISTRY.clear()
    yield
    _REGISTRY.clear()


def test_capability_registers_sync_fn():
    @capability("test_sync", "同步测试函数")
    def sync_fn(x: str) -> str:
        return x

    caps = get_all_capabilities()
    assert len(caps) == 1
    assert caps[0].name == "test_sync"
    assert caps[0].description == "同步测试函数"


def test_capability_registers_async_fn():
    @capability("test_async", "异步测试函数")
    async def async_fn(n: int) -> int:
        return n

    caps = get_all_capabilities()
    assert caps[0].name == "test_async"


def test_capability_extracts_parameters():
    @capability("test_params", "带参数的函数")
    async def fn(path: str, count: int = 10) -> dict:
        return {}

    cap = get_all_capabilities()[0]
    param_names = [p.name for p in cap.parameters]
    assert "path" in param_names
    assert "count" in param_names

    path_param = next(p for p in cap.parameters if p.name == "path")
    assert path_param.required is True

    count_param = next(p for p in cap.parameters if p.name == "count")
    assert count_param.required is False
    assert count_param.default == 10


@pytest.mark.asyncio
async def test_invoke_async():
    @capability("add", "加法")
    async def add(a: int, b: int) -> int:
        return a + b

    result = await invoke("add", {"a": 3, "b": 4})
    assert result == 7


@pytest.mark.asyncio
async def test_invoke_sync():
    @capability("echo", "回声")
    def echo(msg: str) -> str:
        return msg

    result = await invoke("echo", {"msg": "hello"})
    assert result == "hello"


@pytest.mark.asyncio
async def test_invoke_unknown_raises():
    with pytest.raises(ValueError, match="未知 capability"):
        await invoke("no_such_thing", {})
