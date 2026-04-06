"""
domain/agent/service/graph_builder.py

根据 GraphEntity 配置动态构建 LangGraph StateGraph。
支持 ALWAYS、ON_SUCCESS、ON_FAILURE 三种边类型。
LLM 实例通过 LLMGateway 注入，不依赖具体 SDK。
"""

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict

from server.domain.agent.entity.agent_entity import EdgeCondition, GraphEntity
from server.domain.agent.gateway.llm_gateway import LLMGateway
from server.domain.worker.gateway.worker_gateway import WorkerGateway


class GraphState(TypedDict):
    messages: list
    current_node: str
    tool_results: dict


def build_graph(
    graph_entity: GraphEntity,
    worker: WorkerGateway,
    llm_factory: LLMGateway,
) -> CompiledStateGraph:
    """
    根据配置动态构建并编译 LangGraph。
    依赖 WorkerGateway（工具调用）和 LLMGateway（LLM 构建），均为抽象接口。
    """
    sg = StateGraph(GraphState)

    # ── 注册节点 ────────────────────────────────────────────
    for agent in graph_entity.agents:
        llm = llm_factory.build(agent)
        tools = _build_tools(agent.tools, worker)
        sg.add_node(agent.id, _make_node_fn(agent, llm, tools, worker))

    # ── 注册边 ─────────────────────────────────────────────
    sg.set_entry_point(graph_entity.entry_node)

    # 按 from_node 分组处理，避免同一节点多次 add_conditional_edges
    from itertools import groupby
    sorted_edges = sorted(graph_entity.edges, key=lambda e: e.from_node)
    for from_node, group in groupby(sorted_edges, key=lambda e: e.from_node):
        outgoing = list(group)
        has_conditional = any(
            e.condition in (EdgeCondition.ON_SUCCESS, EdgeCondition.ON_FAILURE, EdgeCondition.CONDITIONAL)
            for e in outgoing
        )
        if has_conditional:
            sg.add_conditional_edges(from_node, _make_condition_router(outgoing))
        else:
            # 全部是 ALWAYS 边
            for edge in outgoing:
                sg.add_edge(edge.from_node, edge.to_node)

    # 无出边的节点 → END
    has_outgoing = {e.from_node for e in graph_entity.edges}
    for agent in graph_entity.agents:
        if agent.id not in has_outgoing:
            sg.add_edge(agent.id, END)

    return sg.compile()


def _make_node_fn(agent, llm, tools, worker: WorkerGateway):
    async def node_fn(state: GraphState) -> GraphState:
        from langchain_core.messages import SystemMessage
        messages = [SystemMessage(content=agent.system_prompt)] + state["messages"]
        response = await (llm.bind_tools(tools) if tools else llm).ainvoke(messages)

        tool_results = dict(state.get("tool_results", {}))
        if hasattr(response, "tool_calls") and response.tool_calls:
            for tc in response.tool_calls:
                tool_results[tc["id"]] = await worker.invoke(tc["name"], tc["args"])

        return {
            "messages": list(state["messages"]) + [response],
            "current_node": agent.id,
            "tool_results": tool_results,
        }
    return node_fn


def _make_condition_router(outgoing_edges):
    success_targets = [e.to_node for e in outgoing_edges if e.condition == EdgeCondition.ON_SUCCESS]
    failure_targets = [e.to_node for e in outgoing_edges if e.condition == EdgeCondition.ON_FAILURE]
    always_targets  = [e.to_node for e in outgoing_edges if e.condition == EdgeCondition.ALWAYS]

    def router(state: GraphState) -> str:
        if success_targets:
            return success_targets[0]
        if always_targets:
            return always_targets[0]
        return END
    return router


def _build_tools(tool_names: list[str], worker: WorkerGateway) -> list[dict]:
    caps = {c.name: c for c in worker.list_capabilities()}
    return [caps[n].to_tool_schema() for n in tool_names if n in caps]
