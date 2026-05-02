"""
domain/agent/agent_runtime.py

AgentRuntime：单个 Agent 配置的一次上下文对话运行循环。
按 Step -> Decide -> Execute -> Transition -> StepN 驱动 LLM 推理与工具调用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage, ToolMessage

from server.support.app_logging import get_logger, log_ai_error, log_ai_request, log_ai_response, log_tool_event


class RuntimeStep(str, Enum):
    STEP = "step"
    DECIDE = "decide"
    EXECUTE = "execute"
    TRANSITION = "transition"
    FINALIZE = "finalize"
    DONE = "done"


@dataclass
class RuntimeState:
    messages: list
    current_step: RuntimeStep = RuntimeStep.STEP
    pending_tools: list = field(default_factory=list)
    last_response: Any = None
    tool_results: dict = field(default_factory=dict)
    round: int = 0
    done: bool = False


@dataclass(frozen=True)
class StepDecision:
    next_step: RuntimeStep
    reason: str


def decide_next_step(state: RuntimeState, max_rounds: int = 8) -> StepDecision:
    """根据当前状态决定下一个运行步骤。"""
    if state.done:
        return StepDecision(RuntimeStep.DONE, "state_marked_done")

    if state.current_step == RuntimeStep.STEP:
        return StepDecision(RuntimeStep.DECIDE, "bootstrap_complete")

    if state.current_step == RuntimeStep.DECIDE:
        if state.pending_tools:
            return StepDecision(RuntimeStep.EXECUTE, "llm_requested_tool")
        return StepDecision(RuntimeStep.DONE, "llm_returned_final_text")

    if state.current_step == RuntimeStep.EXECUTE:
        return StepDecision(RuntimeStep.TRANSITION, "tool_execution_complete")

    if state.current_step == RuntimeStep.TRANSITION:
        if state.pending_tools:
            return StepDecision(RuntimeStep.EXECUTE, "more_pending_tools")
        last_had_tools = bool(getattr(state.last_response, "tool_calls", None))
        if last_had_tools:
            if state.round >= max_rounds:
                return StepDecision(RuntimeStep.FINALIZE, "tool_round_limit_reached")
            return StepDecision(RuntimeStep.DECIDE, "continue_reasoning")
        return StepDecision(RuntimeStep.DONE, "no_more_actions")

    if state.current_step == RuntimeStep.FINALIZE:
        return StepDecision(RuntimeStep.DONE, "finalize_complete")

    return StepDecision(RuntimeStep.DONE, "unknown_state")


_FINALIZE_PROMPT = "请根据以上工具调用结果，给出最终回答。"
logger = get_logger(__name__)


class AgentRuntime:
    """
    单节点 AgentRuntime。

    run(init_messages) 是 async generator，按步骤驱动推理与执行。
    该类只表示上下文对话运行时，不是可独立调度、可持久控制的 Agent 本体。
    对外仍保持 text / tool_start / tool_end 事件语义。
    """

    def __init__(
        self,
        node_id: str,
        agent_name: str,
        provider: str,
        model: str,
        llm: Any,
        tools: list,
        worker: Any,
        work_dir: str,
        workspace_root: str = "",
        max_rounds: int = 8,
    ) -> None:
        self._node_id = node_id
        self._agent_name = agent_name
        self._provider = provider
        self._model = model
        self._llm = llm
        self._bound = llm.bind_tools(tools) if tools else llm
        self._worker = worker
        self._context = {
            "work_dir": work_dir,
            "workspace_root": workspace_root or work_dir,
        }
        self._max_rounds = max_rounds

    async def run(self, init_messages: list) -> AsyncGenerator[dict, None]:
        state = RuntimeState(messages=list(init_messages))

        while state.current_step != RuntimeStep.DONE:
            # 内部步骤变更不对外暴露，减少前端干扰
            # yield {
            #     "type": "step_changed",
            #     "node": self._node_id,
            #     "step": state.current_step.value,
            # }

            if state.current_step == RuntimeStep.STEP:
                state.current_step = decide_next_step(state, self._max_rounds).next_step
                continue

            if state.current_step == RuntimeStep.DECIDE:
                async for event in self._handle_decide(state):
                    yield event
                state.current_step = decide_next_step(state, self._max_rounds).next_step
                continue

            if state.current_step == RuntimeStep.EXECUTE:
                async for event in self._handle_execute(state):
                    yield event
                state.current_step = decide_next_step(state, self._max_rounds).next_step
                continue

            if state.current_step == RuntimeStep.TRANSITION:
                state.current_step = decide_next_step(state, self._max_rounds).next_step
                continue

            if state.current_step == RuntimeStep.FINALIZE:
                async for event in self._handle_finalize(state):
                    yield event
                state.current_step = decide_next_step(state, self._max_rounds).next_step

    async def _handle_decide(self, state: RuntimeState) -> AsyncGenerator[dict, None]:
        """调用 LLM 做一次推理决策。"""
        state.round += 1
        log_ai_request(
            logger=logger,
            phase="decide",
            agent_name=self._agent_name,
            node_id=self._node_id,
            provider=self._provider,
            model=self._model,
            messages=state.messages,
            extra={"round": state.round, "step": RuntimeStep.DECIDE.value},
        )
        acc = None
        try:
            async for chunk in self._bound.astream(state.messages):
                acc = chunk if acc is None else acc + chunk
                if chunk.content:
                    yield {"type": "text", "node": self._node_id, "content": chunk.content}
        except Exception as exc:
            log_ai_error(
                logger=logger,
                phase="decide",
                agent_name=self._agent_name,
                node_id=self._node_id,
                error=exc,
                extra={"round": state.round, "step": RuntimeStep.DECIDE.value},
            )
            raise

        state.last_response = acc
        state.messages.append(acc)
        state.pending_tools = list(getattr(acc, "tool_calls", None) or [])
        log_ai_response(
            logger=logger,
            phase="decide",
            agent_name=self._agent_name,
            node_id=self._node_id,
            provider=self._provider,
            model=self._model,
            response=acc,
            extra={
                "round": state.round,
                "step": RuntimeStep.DECIDE.value,
                "tool_call_count": len(state.pending_tools),
            },
        )

    async def _handle_execute(self, state: RuntimeState) -> AsyncGenerator[dict, None]:
        """执行一个待处理的工具调用。"""
        tool_call = state.pending_tools.pop(0)
        tool_name = tool_call["name"]

        yield {"type": "tool_start", "node": self._node_id, "tool": tool_name}
        log_tool_event(
            logger=logger,
            node_id=self._node_id,
            agent_name=self._agent_name,
            tool_name=tool_name,
            status="start",
            args=tool_call["args"],
        )
        result = await self._worker.invoke(tool_name, tool_call["args"], self._context)
        state.tool_results[tool_call["id"]] = result
        state.messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
        log_tool_event(
            logger=logger,
            node_id=self._node_id,
            agent_name=self._agent_name,
            tool_name=tool_name,
            status="end",
            result=result,
        )
        yield {
            "type": "tool_end",
            "node": self._node_id,
            "tool": tool_name,
            "result": str(result)[:300],
        }

    async def _handle_finalize(self, state: RuntimeState) -> AsyncGenerator[dict, None]:
        """达到工具轮次上限后，触发最终总结。"""
        state.messages.append(HumanMessage(content=_FINALIZE_PROMPT))
        log_ai_request(
            logger=logger,
            phase="finalize",
            agent_name=self._agent_name,
            node_id=self._node_id,
            provider=self._provider,
            model=self._model,
            messages=state.messages,
            extra={"round": state.round, "step": RuntimeStep.FINALIZE.value},
        )
        acc = None
        try:
            async for chunk in self._llm.astream(state.messages):
                acc = chunk if acc is None else acc + chunk
                if chunk.content:
                    yield {"type": "text", "node": self._node_id, "content": chunk.content}
        except Exception as exc:
            log_ai_error(
                logger=logger,
                phase="finalize",
                agent_name=self._agent_name,
                node_id=self._node_id,
                error=exc,
                extra={"round": state.round, "step": RuntimeStep.FINALIZE.value},
            )
            raise

        state.last_response = acc
        state.done = True
        log_ai_response(
            logger=logger,
            phase="finalize",
            agent_name=self._agent_name,
            node_id=self._node_id,
            provider=self._provider,
            model=self._model,
            response=acc,
            extra={"round": state.round, "step": RuntimeStep.FINALIZE.value},
        )
