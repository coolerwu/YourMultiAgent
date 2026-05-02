"""
tests/domain/agent/test_agent_runtime.py

AgentRuntime 单测：覆盖 Step -> Decide -> Execute -> Transition 调用链。
"""

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from server.domain.agent.agent_runtime import AgentRuntime, RuntimeState, RuntimeStep, decide_next_step


class _Chunk:
    def __init__(self, content: str = "", tool_calls: list[dict] | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls or []

    def __add__(self, other):
        return _Chunk(
            content=self.content + getattr(other, "content", ""),
            tool_calls=getattr(other, "tool_calls", self.tool_calls),
        )


class _BoundLLM:
    def __init__(self, parent) -> None:
        self._parent = parent

    async def astream(self, messages):
        self._parent.bound_messages.append(messages)
        response = self._parent.bound_responses.pop(0)
        yield response


class _FakeLLM:
    def __init__(self, *, bound_responses: list[_Chunk], final_responses: list[_Chunk] | None = None) -> None:
        self.bound_responses = list(bound_responses)
        self.final_responses = list(final_responses or [])
        self.bound_messages = []
        self.final_messages = []

    def bind_tools(self, _tools):
        return _BoundLLM(self)

    async def astream(self, messages):
        self.final_messages.append(messages)
        response = self.final_responses.pop(0)
        yield response


def test_decide_next_step_returns_finalize_when_tool_round_limit_reached():
    state = RuntimeState(
        messages=[],
        current_step=RuntimeStep.TRANSITION,
        last_response=_Chunk(tool_calls=[{"id": "call-1", "name": "read_file", "args": {}}]),
        round=1,
    )

    decision = decide_next_step(state, max_rounds=1)

    assert decision.next_step == RuntimeStep.FINALIZE
    assert decision.reason == "tool_round_limit_reached"


@pytest.mark.asyncio
async def test_agent_runtime_runs_step_decide_execute_transition_decide_chain():
    llm = _FakeLLM(
        bound_responses=[
            _Chunk(
                content="先读取文件",
                tool_calls=[{"id": "call-1", "name": "read_file", "args": {"path": "README.md"}}],
            ),
            _Chunk(content="读取完成，开始总结", tool_calls=[]),
        ]
    )
    worker = AsyncMock()
    worker.invoke = AsyncMock(return_value="README 内容")
    runtime = AgentRuntime(
        node_id="writer",
        agent_name="Writer",
        provider="anthropic",
        model="claude-sonnet-4-6",
        llm=llm,
        tools=[{"name": "read_file"}],
        worker=worker,
        work_dir="/tmp/demo",
        workspace_root="/tmp/demo",
        max_rounds=3,
    )

    events = [event async for event in runtime.run([HumanMessage(content="分析 README")])]

    # step_changed 事件已移除，不再对外暴露
    assert not any(event["type"] == "step_changed" for event in events)
    assert any(event["type"] == "tool_start" and event["tool"] == "read_file" for event in events)
    assert any(event["type"] == "tool_end" and event["tool"] == "read_file" for event in events)
    assert any(event["type"] == "text" and "读取完成" in event["content"] for event in events)
    worker.invoke.assert_awaited_once_with(
        "read_file",
        {"path": "README.md"},
        {"work_dir": "/tmp/demo", "workspace_root": "/tmp/demo"},
    )


@pytest.mark.asyncio
async def test_agent_runtime_finalizes_after_max_rounds():
    llm = _FakeLLM(
        bound_responses=[
            _Chunk(
                content="先读取文件",
                tool_calls=[{"id": "call-1", "name": "read_file", "args": {"path": "README.md"}}],
            )
        ],
        final_responses=[_Chunk(content="最终总结", tool_calls=[])],
    )
    worker = AsyncMock()
    worker.invoke = AsyncMock(return_value="README 内容")
    runtime = AgentRuntime(
        node_id="writer",
        agent_name="Writer",
        provider="anthropic",
        model="claude-sonnet-4-6",
        llm=llm,
        tools=[{"name": "read_file"}],
        worker=worker,
        work_dir="/tmp/demo",
        workspace_root="/tmp/demo",
        max_rounds=1,
    )

    events = [event async for event in runtime.run([HumanMessage(content="分析 README")])]

    # step_changed 事件已移除，不再对外暴露
    assert not any(event["type"] == "step_changed" for event in events)
    assert events[-1]["type"] == "text"
    assert events[-1]["content"] == "最终总结"
