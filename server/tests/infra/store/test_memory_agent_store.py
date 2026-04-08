"""
tests/infra/store/test_memory_agent_store.py

MemoryAgentStore CRUD 单测。
"""

import pytest
from server.domain.agent.agent_entity import GraphEntity
from server.infra.store.memory_agent_store import MemoryAgentStore


def _make_graph(gid="g1", name="test"):
    return GraphEntity(id=gid, name=name, entry_node="n1", agents=[], edges=[])


@pytest.mark.asyncio
async def test_save_and_find_by_id():
    store = MemoryAgentStore()
    graph = _make_graph("g1", "图1")
    await store.save(graph)
    result = await store.find_by_id("g1")
    assert result is not None
    assert result.name == "图1"


@pytest.mark.asyncio
async def test_find_by_id_not_found():
    store = MemoryAgentStore()
    result = await store.find_by_id("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_find_all():
    store = MemoryAgentStore()
    await store.save(_make_graph("g1"))
    await store.save(_make_graph("g2"))
    all_graphs = await store.find_all()
    assert len(all_graphs) == 2


@pytest.mark.asyncio
async def test_save_overwrites_existing():
    store = MemoryAgentStore()
    await store.save(_make_graph("g1", "原始"))
    await store.save(_make_graph("g1", "更新"))
    result = await store.find_by_id("g1")
    assert result.name == "更新"


@pytest.mark.asyncio
async def test_delete_existing():
    store = MemoryAgentStore()
    await store.save(_make_graph("g1"))
    ok = await store.delete("g1")
    assert ok is True
    assert await store.find_by_id("g1") is None


@pytest.mark.asyncio
async def test_delete_nonexistent():
    store = MemoryAgentStore()
    ok = await store.delete("nonexistent")
    assert ok is False
