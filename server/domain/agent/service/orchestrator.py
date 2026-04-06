"""
domain/agent/service/orchestrator.py

执行 Agent 图，流式 yield SSE 事件字符串。
依赖 WorkerGateway 和 LLMGateway，均为抽象接口，不涉及具体实现。
"""

import json
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage

from server.domain.agent.entity.agent_entity import GraphEntity
from server.domain.agent.gateway.llm_gateway import LLMGateway
from server.domain.agent.service.graph_builder import GraphState, build_graph
from server.domain.worker.gateway.worker_gateway import WorkerGateway


class AgentOrchestrator:
    def __init__(self, worker: WorkerGateway, llm_factory: LLMGateway) -> None:
        self._worker = worker
        self._llm_factory = llm_factory

    async def run(
        self, graph: GraphEntity, user_message: str
    ) -> AsyncGenerator[str, None]:
        compiled = build_graph(graph, self._worker, self._llm_factory)
        init_state: GraphState = {
            "messages": [HumanMessage(content=user_message)],
            "current_node": graph.entry_node,
            "tool_results": {},
        }

        async for event in compiled.astream_events(init_state, version="v2"):
            kind = event.get("event")
            if kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    node_id = event.get("metadata", {}).get("langgraph_node", "")
                    yield _sse({"node": node_id, "type": "text", "content": chunk.content})
            elif kind == "on_tool_start":
                yield _sse({"node": "", "type": "tool_start", "content": f"调用工具: {event['name']}"})
            elif kind == "on_tool_end":
                yield _sse({"node": "", "type": "tool_end", "content": f"工具完成: {event['name']}"})

        yield _sse({"type": "done", "content": ""})


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
