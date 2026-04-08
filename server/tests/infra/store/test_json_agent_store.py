"""
tests/infra/store/test_json_agent_store.py

JsonAgentStore 单元测试：使用 tmp_path fixture，覆盖 CRUD + 重启恢复 + enum 序列化。
"""

import pytest

from server.domain.agent.agent_entity import (
    AgentEntity, EdgeCondition, GraphEdge, GraphEntity, LLMProvider, WorkspaceEntity,
)
from server.infra.store.json_agent_store import JsonAgentStore
from server.infra.store.json_workspace_store import JsonWorkspaceStore


def _make_graph(graph_id="g-1") -> GraphEntity:
    return GraphEntity(
        id=graph_id,
        name="Test Graph",
        entry_node="a1",
        workspace_id="ws-1",
        agents=[
            AgentEntity(
                id="a1", name="Writer",
                provider=LLMProvider.ANTHROPIC,
                model="claude-sonnet-4-6",
                system_prompt="你是写作助手",
                tools=["read_file"],
                work_subdir="writer",
            )
        ],
        edges=[
            GraphEdge(from_node="a1", to_node="a2", condition=EdgeCondition.ON_SUCCESS)
        ],
    )


@pytest.mark.asyncio
async def test_save_and_find_by_id(tmp_path):
    ws_store = JsonWorkspaceStore(tmp_path)
    await ws_store.save(WorkspaceEntity(id="ws-1", name="WS", work_dir="/tmp/ws"))
    store = JsonAgentStore(tmp_path)
    graph = _make_graph()
    await store.save(graph)
    result = await store.find_by_id("g-1")
    assert result is not None
    assert result.name == "Test Graph"
    assert result.workspace_id == "ws-1"


@pytest.mark.asyncio
async def test_enum_roundtrip(tmp_path):
    """enum 序列化后重启可正确还原"""
    ws_store = JsonWorkspaceStore(tmp_path)
    await ws_store.save(WorkspaceEntity(id="ws-1", name="WS", work_dir="/tmp/ws"))
    store = JsonAgentStore(tmp_path)
    await store.save(_make_graph())

    # 重建 store（模拟重启）
    store2 = JsonAgentStore(tmp_path)
    result = await store2.find_by_id("g-1")
    assert result.agents[0].provider == LLMProvider.ANTHROPIC
    assert result.edges[0].condition == EdgeCondition.ON_SUCCESS


@pytest.mark.asyncio
async def test_data_persists_across_instances(tmp_path):
    """文件持久化：新实例可读到旧实例写入的数据"""
    ws_store = JsonWorkspaceStore(tmp_path)
    await ws_store.save(WorkspaceEntity(id="ws-1", name="WS", work_dir="/tmp/ws"))
    store1 = JsonAgentStore(tmp_path)
    await store1.save(_make_graph("g-persist"))

    store2 = JsonAgentStore(tmp_path)
    result = await store2.find_by_id("g-persist")
    assert result is not None
    assert result.name == "Test Graph"


@pytest.mark.asyncio
async def test_find_by_id_not_found(tmp_path):
    store = JsonAgentStore(tmp_path)
    assert await store.find_by_id("ghost") is None


@pytest.mark.asyncio
async def test_find_all(tmp_path):
    ws_store = JsonWorkspaceStore(tmp_path)
    await ws_store.save(WorkspaceEntity(id="ws-1", name="WS", work_dir="/tmp/ws"))
    store = JsonAgentStore(tmp_path)
    await store.save(_make_graph("g-1"))
    await store.save(_make_graph("g-2"))
    result = await store.find_all()
    assert len(result) == 2


@pytest.mark.asyncio
async def test_save_overwrites(tmp_path):
    ws_store = JsonWorkspaceStore(tmp_path)
    await ws_store.save(WorkspaceEntity(id="ws-1", name="WS", work_dir="/tmp/ws"))
    store = JsonAgentStore(tmp_path)
    await store.save(_make_graph())
    g = _make_graph()
    g.name = "Updated"
    await store.save(g)
    result = await store.find_by_id("g-1")
    assert result.name == "Updated"


@pytest.mark.asyncio
async def test_delete(tmp_path):
    ws_store = JsonWorkspaceStore(tmp_path)
    await ws_store.save(WorkspaceEntity(id="ws-1", name="WS", work_dir="/tmp/ws"))
    store = JsonAgentStore(tmp_path)
    await store.save(_make_graph())
    ok = await store.delete("g-1")
    assert ok is True
    assert await store.find_by_id("g-1") is None


@pytest.mark.asyncio
async def test_delete_nonexistent(tmp_path):
    store = JsonAgentStore(tmp_path)
    assert await store.delete("ghost") is False


@pytest.mark.asyncio
async def test_save_requires_workspace(tmp_path):
    store = JsonAgentStore(tmp_path)
    graph = _make_graph()
    graph.workspace_id = ""
    with pytest.raises(ValueError, match="workspace_id"):
        await store.save(graph)
