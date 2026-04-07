"""
domain/agent/service/react_loop.py

单节点 ReAct 状态机，负责驱动 LLM 推理 + 工具调用循环。
不依赖 LangGraph，直接 yield dict 事件供上层透传给客户端。

状态机转换规则（next_event）：
  done=True               → DONE
  pending_tools 非空      → NEED_TOOL
  last_response is None   → NEED_REASON  (首次调用)
  last_response 有 tool_calls（工具刚处理完）:
    round >= max_rounds   → NEED_FINALIZE（超限，额外总结调用）
    otherwise             → NEED_REASON
  last_response 无 tool_calls → DONE    (LLM 给出纯文本，自然结束)

事件类型（yield dict）：
  text        — {"type": "text",       "node": ..., "content": ...}
  tool_start  — {"type": "tool_start", "node": ..., "tool": ...}
  tool_end    — {"type": "tool_end",   "node": ..., "tool": ..., "result": ...}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Optional

from langchain_core.messages import HumanMessage, ToolMessage


class LoopEvent(str, Enum):
    NEED_REASON   = "need_reason"    # 调用 LLM 推理
    NEED_TOOL     = "need_tool"      # 执行一个工具调用
    NEED_FINALIZE = "need_finalize"  # 超出最大轮次，强制总结
    DONE          = "done"           # 循环结束


@dataclass
class LoopState:
    messages: list
    pending_tools: list       = field(default_factory=list)  # 待执行的 tool_calls
    last_response: Any        = None
    tool_results: dict        = field(default_factory=dict)
    round: int                = 0
    done: bool                = False


def next_event(state: LoopState, max_rounds: int = 8) -> LoopEvent:
    """根据当前状态决定下一个事件类型（纯函数，无副作用）。"""
    if state.done:
        return LoopEvent.DONE

    # 仍有待执行工具
    if state.pending_tools:
        return LoopEvent.NEED_TOOL

    # 首次调用，还没有任何 LLM 响应
    if state.last_response is None:
        return LoopEvent.NEED_REASON

    # 上一轮 LLM 有 tool_calls，说明工具已执行完毕，需要继续推理
    last_had_tools = bool(
        getattr(state.last_response, "tool_calls", None)
    )
    if last_had_tools:
        if state.round >= max_rounds:
            return LoopEvent.NEED_FINALIZE
        return LoopEvent.NEED_REASON

    # 上一轮 LLM 返回纯文本 → 自然结束
    return LoopEvent.DONE


_FINALIZE_PROMPT = "请根据以上工具调用结果，给出最终回答。"


class ReactLoop:
    """
    单节点 ReAct 状态机。

    run(init_messages) 是 async generator，按顺序 yield dict 事件。
    调用方只需 async for event in loop.run(messages) 即可。
    """

    def __init__(
        self,
        node_id: str,
        llm: Any,                         # LangChain BaseChatModel
        tools: list,                       # LangChain tool schema list
        worker: Any,                       # WorkerGateway
        work_dir: str,
        workspace_root: str = "",
        max_rounds: int = 8,
    ) -> None:
        self._node_id   = node_id
        self._llm       = llm
        self._bound     = llm.bind_tools(tools) if tools else llm
        self._worker    = worker
        self._context   = {
            "work_dir": work_dir,
            "workspace_root": workspace_root or work_dir,
        }
        self._max_rounds = max_rounds

    async def run(
        self,
        init_messages: list,
    ) -> AsyncGenerator[dict, None]:
        state = LoopState(messages=list(init_messages))

        while True:
            event = next_event(state, self._max_rounds)

            if event == LoopEvent.DONE:
                break

            elif event == LoopEvent.NEED_REASON:
                async for e in self._handle_reason(state):
                    yield e

            elif event == LoopEvent.NEED_TOOL:
                async for e in self._handle_tool(state):
                    yield e

            elif event == LoopEvent.NEED_FINALIZE:
                async for e in self._handle_finalize(state):
                    yield e

    # ── 私有处理器 ────────────────────────────────────────────

    async def _handle_reason(
        self, state: LoopState
    ) -> AsyncGenerator[dict, None]:
        """调用 LLM（带工具绑定），流式输出文本，累积完整响应。"""
        state.round += 1
        acc = None
        async for chunk in self._bound.astream(state.messages):
            acc = chunk if acc is None else acc + chunk
            if chunk.content:
                yield {"type": "text", "node": self._node_id, "content": chunk.content}

        state.last_response = acc
        state.messages.append(acc)

        # 提取 tool_calls 到待执行队列
        tool_calls = getattr(acc, "tool_calls", None) or []
        state.pending_tools = list(tool_calls)

    async def _handle_tool(
        self, state: LoopState
    ) -> AsyncGenerator[dict, None]:
        """弹出第一个待执行工具，调用 worker，结果包装为 ToolMessage。"""
        tc = state.pending_tools.pop(0)
        name = tc["name"]

        yield {"type": "tool_start", "node": self._node_id, "tool": name}
        result = await self._worker.invoke(name, tc["args"], self._context)
        state.tool_results[tc["id"]] = result
        state.messages.append(
            ToolMessage(content=str(result), tool_call_id=tc["id"])
        )
        yield {
            "type": "tool_end",
            "node": self._node_id,
            "tool": name,
            "result": str(result)[:300],
        }

    async def _handle_finalize(
        self, state: LoopState
    ) -> AsyncGenerator[dict, None]:
        """超出最大轮次时，附加提示语，额外调用 LLM（不绑工具）做最终总结。"""
        state.messages.append(HumanMessage(content=_FINALIZE_PROMPT))
        acc = None
        async for chunk in self._llm.astream(state.messages):
            acc = chunk if acc is None else acc + chunk
            if chunk.content:
                yield {"type": "text", "node": self._node_id, "content": chunk.content}

        state.last_response = acc
        state.done = True
