"""
app/agent/agent_app_service.py

Agent 应用服务：编排 Command/Query，协调 domain 与 infra。
不包含业务规则，只做流程编排。
"""

import uuid
from typing import AsyncGenerator

from server.app.agent.command.create_agent_cmd import CreateGraphCmd, UpdateGraphCmd
from server.app.agent.command.run_agent_cmd import RunGraphCmd
from server.app.agent.query.list_agents_qry import AgentNodeVO, GraphEdgeVO, GraphVO
from server.domain.agent.entity.agent_entity import (
    AgentEntity,
    GraphEdge,
    GraphEntity,
)
from server.domain.agent.gateway.agent_gateway import AgentGateway
from server.domain.agent.service.orchestrator import AgentOrchestrator


class AgentAppService:
    def __init__(self, gateway: AgentGateway, orchestrator: AgentOrchestrator) -> None:
        self._gateway = gateway
        self._orchestrator = orchestrator

    # ── Commands ──────────────────────────────────────────────

    async def create_graph(self, cmd: CreateGraphCmd) -> GraphVO:
        graph = GraphEntity(
            id=str(uuid.uuid4()),
            name=cmd.name,
            entry_node=cmd.entry_node,
            agents=[
                AgentEntity(
                    id=a.id, name=a.name, provider=a.provider,
                    model=a.model, system_prompt=a.system_prompt,
                    temperature=a.temperature, max_tokens=a.max_tokens,
                    tools=a.tools,
                )
                for a in cmd.agents
            ],
            edges=[
                GraphEdge(
                    from_node=e.from_node, to_node=e.to_node,
                    condition=e.condition, condition_expr=e.condition_expr,
                )
                for e in cmd.edges
            ],
        )
        await self._gateway.save(graph)
        return _to_vo(graph)

    async def update_graph(self, cmd: UpdateGraphCmd) -> GraphVO:
        graph = GraphEntity(
            id=cmd.graph_id,
            name=cmd.name,
            entry_node=cmd.entry_node,
            agents=[
                AgentEntity(
                    id=a.id, name=a.name, provider=a.provider,
                    model=a.model, system_prompt=a.system_prompt,
                    temperature=a.temperature, max_tokens=a.max_tokens,
                    tools=a.tools,
                )
                for a in cmd.agents
            ],
            edges=[
                GraphEdge(
                    from_node=e.from_node, to_node=e.to_node,
                    condition=e.condition, condition_expr=e.condition_expr,
                )
                for e in cmd.edges
            ],
        )
        await self._gateway.save(graph)
        return _to_vo(graph)

    async def delete_graph(self, graph_id: str) -> bool:
        return await self._gateway.delete(graph_id)

    async def run_graph(self, cmd: RunGraphCmd) -> AsyncGenerator[str, None]:
        """流式执行，yield SSE 事件字符串"""
        graph = await self._gateway.find_by_id(cmd.graph_id)
        if graph is None:
            raise ValueError(f"Graph 不存在: {cmd.graph_id}")
        async for chunk in self._orchestrator.run(graph, cmd.user_message):
            yield chunk

    # ── Queries ───────────────────────────────────────────────

    async def list_graphs(self) -> list[GraphVO]:
        graphs = await self._gateway.find_all()
        return [_to_vo(g) for g in graphs]

    async def get_graph(self, graph_id: str) -> GraphVO | None:
        graph = await self._gateway.find_by_id(graph_id)
        return _to_vo(graph) if graph else None


# ── 私有转换函数 ───────────────────────────────────────────────

def _to_vo(graph: GraphEntity) -> GraphVO:
    return GraphVO(
        id=graph.id,
        name=graph.name,
        entry_node=graph.entry_node,
        agents=[
            AgentNodeVO(
                id=a.id, name=a.name, provider=a.provider,
                model=a.model, system_prompt=a.system_prompt,
                temperature=a.temperature, max_tokens=a.max_tokens,
                tools=a.tools,
            )
            for a in graph.agents
        ],
        edges=[
            GraphEdgeVO(
                from_node=e.from_node, to_node=e.to_node,
                condition=e.condition, condition_expr=e.condition_expr,
            )
            for e in graph.edges
        ],
    )
