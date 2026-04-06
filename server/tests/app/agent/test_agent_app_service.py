"""
tests/app/agent/test_agent_app_service.py

AgentAppService 单测：mock gateway 和 orchestrator，不涉及真实 LLM 或存储。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from server.app.agent.agent_app_service import AgentAppService
from server.app.agent.command.create_agent_cmd import AgentNodeCmd, CreateGraphCmd, GraphEdgeCmd
from server.app.agent.command.run_agent_cmd import RunGraphCmd
from server.domain.agent.entity.agent_entity import EdgeCondition, LLMProvider


def _make_create_cmd(name="测试图"):
    return CreateGraphCmd(
        name=name,
        entry_node="n1",
        agents=[
            AgentNodeCmd(
                id="n1", name="Agent1",
                provider=LLMProvider.ANTHROPIC,
                model="claude-sonnet-4-6",
                system_prompt="你是助手",
            )
        ],
        edges=[],
    )


@pytest.fixture
def mock_gateway():
    gw = AsyncMock()
    gw.find_all.return_value = []
    gw.find_by_id.return_value = None
    return gw


@pytest.fixture
def mock_orchestrator():
    return MagicMock()


@pytest.fixture
def svc(mock_gateway, mock_orchestrator):
    return AgentAppService(mock_gateway, mock_orchestrator)


@pytest.mark.asyncio
async def test_create_graph_calls_save(svc, mock_gateway):
    vo = await svc.create_graph(_make_create_cmd("新图"))
    assert vo.name == "新图"
    assert vo.entry_node == "n1"
    mock_gateway.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_graph_generates_id(svc):
    vo1 = await svc.create_graph(_make_create_cmd())
    vo2 = await svc.create_graph(_make_create_cmd())
    assert vo1.id != vo2.id


@pytest.mark.asyncio
async def test_list_graphs_empty(svc, mock_gateway):
    mock_gateway.find_all.return_value = []
    result = await svc.list_graphs()
    assert result == []


@pytest.mark.asyncio
async def test_get_graph_not_found(svc, mock_gateway):
    mock_gateway.find_by_id.return_value = None
    result = await svc.get_graph("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_delete_graph_delegates(svc, mock_gateway):
    mock_gateway.delete.return_value = True
    ok = await svc.delete_graph("g1")
    assert ok is True
    mock_gateway.delete.assert_awaited_once_with("g1")


@pytest.mark.asyncio
async def test_run_graph_not_found_raises(svc, mock_gateway):
    mock_gateway.find_by_id.return_value = None
    cmd = RunGraphCmd(graph_id="bad_id", user_message="hello")

    async def collect():
        async for _ in svc.run_graph(cmd):
            pass

    with pytest.raises(ValueError, match="Graph 不存在"):
        await collect()
