"""
tests/infra/store/test_memory_workspace_store.py

MemoryWorkspaceStore 单元测试：CRUD 正常路径 + 边界 case。
"""

import pytest

from server.domain.agent.agent_entity import LLMProvider, WorkspaceEntity
from server.infra.store.memory_workspace_store import MemoryWorkspaceStore


def _make_ws(ws_id="ws-1", name="Test WS") -> WorkspaceEntity:
    return WorkspaceEntity(
        id=ws_id,
        name=name,
        work_dir="~/projects/test",
        default_provider=LLMProvider.OPENAI,
        default_model="gpt-4o",
    )


@pytest.mark.asyncio
async def test_save_and_find_by_id():
    store = MemoryWorkspaceStore()
    ws = _make_ws()
    await store.save(ws)
    result = await store.find_by_id("ws-1")
    assert result is not None
    assert result.name == "Test WS"


@pytest.mark.asyncio
async def test_find_by_id_not_found():
    store = MemoryWorkspaceStore()
    result = await store.find_by_id("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_find_all_empty():
    store = MemoryWorkspaceStore()
    result = await store.find_all()
    assert result == []


@pytest.mark.asyncio
async def test_find_all_multiple():
    store = MemoryWorkspaceStore()
    await store.save(_make_ws("ws-1", "A"))
    await store.save(_make_ws("ws-2", "B"))
    result = await store.find_all()
    assert len(result) == 2


@pytest.mark.asyncio
async def test_save_overwrites_existing():
    store = MemoryWorkspaceStore()
    ws = _make_ws()
    await store.save(ws)
    updated = WorkspaceEntity(
        id="ws-1", name="Updated", work_dir="~/new",
        default_provider=LLMProvider.OPENAI, default_model="gpt-4o",
    )
    await store.save(updated)
    result = await store.find_by_id("ws-1")
    assert result.name == "Updated"
    assert result.work_dir == "~/new"


@pytest.mark.asyncio
async def test_delete_existing():
    store = MemoryWorkspaceStore()
    await store.save(_make_ws())
    ok = await store.delete("ws-1")
    assert ok is True
    assert await store.find_by_id("ws-1") is None


@pytest.mark.asyncio
async def test_delete_nonexistent():
    store = MemoryWorkspaceStore()
    ok = await store.delete("ghost")
    assert ok is False
