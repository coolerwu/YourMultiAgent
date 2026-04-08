"""
app/agent/workspace_executor.py

Workspace 单编排执行器：
- 先运行 Coordinator 生成拆解计划
- 再按顺序调度多个 Worker
- 共享交接物约定写入 Workspace 根目录下的 shared/

位于 app 层，负责运行流程编排，不承载纯领域规则定义。
"""

from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from server.domain.agent.agent_entity import AgentEntity, ChatSessionEntity, WorkspaceEntity, WorkspaceKind
from server.domain.agent.llm_gateway import LLMGateway
from server.domain.agent.agent_harness import AgentHarness
from server.domain.agent.session_history import build_runtime_messages
from server.domain.worker.capability_entity import CapabilityEntity
from server.domain.worker.worker_gateway import WorkerGateway
from server.support.app_logging import get_logger

_MAX_TOOL_ROUNDS = 8
logger = get_logger(__name__)


class WorkspaceExecutor:
    def __init__(
        self,
        workspace: WorkspaceEntity,
        worker_gateway: WorkerGateway,
        llm_factory: LLMGateway,
        base_work_dir: str = "",
    ) -> None:
        self._workspace = workspace
        self._worker_gateway = worker_gateway
        self._llm_factory = llm_factory
        self._workspace_root = _resolve_workspace_root(workspace, base_work_dir)

    async def run(self, user_message: str, session: ChatSessionEntity) -> AsyncGenerator[dict, None]:
        root = Path(self._workspace_root)
        root.mkdir(parents=True, exist_ok=True)
        (root / "shared").mkdir(parents=True, exist_ok=True)

        if self._workspace.kind == WorkspaceKind.CHAT:
            assistant = self._workspace.coordinator
            if assistant is None:
                raise ValueError("单聊目录尚未配置默认助手")
            async for event in self._stream_agent(
                agent=assistant,
                event_type_prefix="coordinator",
                session=session,
                user_message=user_message,
            ):
                yield event
            yield {"type": "done"}
            return

        coordinator = self._workspace.coordinator
        if coordinator is None:
            raise ValueError("Workspace 尚未配置主控智能体")

        yield {
            "type": "plan_created",
            "coordinator": coordinator.id,
            "coordinator_name": coordinator.name,
        }
        plan_text = ""
        async for event in self._stream_agent(
            agent=coordinator,
            event_type_prefix="coordinator",
            session=session,
            user_message=_build_coordinator_message(user_message, self._workspace.workers),
        ):
            if event.get("type") == "text" and event.get("node") == coordinator.id:
                plan_text += event.get("content", "")
            yield event

        worker_outputs: list[dict[str, str]] = []
        for worker in _ordered_workers(self._workspace.workers):
            assignment = _build_assignment(plan_text, user_message, worker)
            yield {
                "type": "task_assigned",
                "worker": worker.id,
                "worker_name": worker.name,
                "actor_id": coordinator.id,
                "actor_name": coordinator.name,
                "actor_kind": "coordinator",
                "assignment": assignment,
            }
            output = ""
            async for event in self._stream_agent(
                agent=worker,
                event_type_prefix="worker",
                session=session,
                user_message=assignment,
            ):
                if event.get("type") == "text" and event.get("node") == worker.id:
                    output += event.get("content", "")
                yield event
            worker_outputs.append({"worker_name": worker.name, "output": output})
            yield {
                "type": "worker_result",
                "worker": worker.id,
                "worker_name": worker.name,
                "actor_id": worker.id,
                "actor_name": worker.name,
                "actor_kind": "worker",
                "summary": output[:240],
            }

        yield {
            "type": "run_summary",
            "actor_id": coordinator.id,
            "actor_name": coordinator.name,
            "actor_kind": "coordinator",
            "summary": _build_run_summary(plan_text, worker_outputs),
        }
        yield {"type": "done"}

    async def _stream_agent(
        self,
        agent: AgentEntity,
        event_type_prefix: str,
        session: ChatSessionEntity,
        user_message: str,
    ) -> AsyncGenerator[dict, None]:
        llm = self._llm_factory.build(agent, self._workspace)
        capabilities = _build_capabilities(agent.tools, self._worker_gateway)
        tools = [item.to_tool_schema() for item in capabilities]
        work_dir = _resolve_agent_work_dir(self._workspace, self._workspace_root, agent)
        Path(work_dir).mkdir(parents=True, exist_ok=True)

        yield {
            "type": f"{event_type_prefix}_start",
            "node": agent.id,
            "node_name": agent.name,
            "actor_id": agent.id,
            "actor_name": agent.name,
            "actor_kind": event_type_prefix,
        }
        logger.info(
            "agent_run_start workspace=%s node=%s name=%s provider=%s model=%s",
            self._workspace.id,
            agent.id,
            agent.name,
            agent.provider,
            agent.model,
        )
        harness = AgentHarness(
            node_id=agent.id,
            agent_name=agent.name,
            provider=str(agent.provider),
            model=agent.model,
            llm=llm,
            tools=tools,
            worker=self._worker_gateway,
            work_dir=work_dir,
            workspace_root=self._workspace_root,
            max_rounds=_MAX_TOOL_ROUNDS,
        )
        runtime_messages = build_runtime_messages(
            session,
            exclude_latest_user_message=user_message,
        )
        logger.info(
            "agent_run_context workspace=%s node=%s runtime_message_count=%s user_message_chars=%s",
            self._workspace.id,
            agent.id,
            len(runtime_messages),
            len(user_message or ""),
        )
        async for event in harness.run([
            SystemMessage(content=_build_agent_system_prompt(agent, capabilities)),
            *runtime_messages,
            HumanMessage(content=user_message),
        ]):
            yield {
                **event,
                "actor_id": agent.id,
                "actor_name": agent.name,
                "actor_kind": event_type_prefix,
            }
        logger.info(
            "agent_run_end workspace=%s node=%s name=%s provider=%s model=%s",
            self._workspace.id,
            agent.id,
            agent.name,
            agent.provider,
            agent.model,
        )
        yield {
            "type": f"{event_type_prefix}_end",
            "node": agent.id,
            "node_name": agent.name,
            "actor_id": agent.id,
            "actor_name": agent.name,
            "actor_kind": event_type_prefix,
        }


def _build_capabilities(tool_names: list[str], worker: WorkerGateway) -> list[CapabilityEntity]:
    caps = {c.name: c for c in worker.list_capabilities()}
    return [caps[name] for name in tool_names if name in caps]


def _resolve_workspace_root(workspace: WorkspaceEntity, base_work_dir: str) -> str:
    if workspace.work_dir:
        return str(Path(workspace.work_dir).expanduser().resolve())
    if base_work_dir:
        return str(Path(base_work_dir).resolve())
    return str(Path(".").resolve())


def _resolve_agent_work_dir(workspace: WorkspaceEntity, workspace_root: str, agent: AgentEntity) -> str:
    if workspace.kind == WorkspaceKind.CHAT:
        return str(Path(workspace_root).resolve())
    subdir = agent.resolved_work_subdir()
    return str((Path(workspace_root) / subdir).resolve())


def _ordered_workers(workers: list[AgentEntity]) -> list[AgentEntity]:
    return [
        worker
        for _, worker in sorted(
            enumerate(workers),
            key=lambda item: (
                item[1].order if item[1].order > 0 else item[0] + 1,
                item[0],
            ),
        )
    ]


def _build_coordinator_message(user_message: str, workers: list[AgentEntity]) -> str:
    worker_names = "、".join(worker.name for worker in workers) if workers else "暂无 Worker"
    return (
        f"用户任务：{user_message}\n\n"
        f"可用 Worker：{worker_names}\n"
        "请先输出简明任务拆解，说明每个 Worker 负责什么，"
        "并统一要求共享交接物写入当前 Workspace 的 `shared/` 目录，例如 `workspace/<workspace_name>/shared/`。"
    )


def _build_assignment(plan_text: str, user_message: str, worker: AgentEntity) -> str:
    return (
        f"原始任务：{user_message}\n\n"
        f"主控拆解：\n{plan_text or '请根据你的角色独立完成任务。'}\n\n"
        f"你当前负责的角色：{worker.name}\n"
        "请根据以上拆解，仅完成分派给你的那部分工作。"
    )


def _build_run_summary(plan_text: str, worker_outputs: list[dict[str, str]]) -> str:
    lines = ["主控拆解：", plan_text or "无", "", "Worker 结果："]
    for item in worker_outputs:
        lines.append(f"- {item['worker_name']}: {item['output'][:200] or '无输出'}")
    return "\n".join(lines)


def _build_agent_system_prompt(agent: AgentEntity, capabilities: list[CapabilityEntity]) -> str:
    prompt_parts = [agent.system_prompt.strip()]
    capability_block = _build_capability_prompt_block(capabilities)
    if capability_block:
        prompt_parts.append(capability_block)
    return "\n\n".join(item for item in prompt_parts if item)


def _build_capability_prompt_block(capabilities: list[CapabilityEntity]) -> str:
    if not capabilities:
        return ""

    lines = [
        "【工具使用约束】",
        "你只能使用当前已授权的工具；如果工具不足以完成任务，要明确说明缺口，不要虚构执行结果。",
    ]

    browser_caps = [item for item in capabilities if item.name.startswith("browser_")]
    non_browser_caps = [item for item in capabilities if not item.name.startswith("browser_")]

    if browser_caps:
        browser_names = "、".join(item.name for item in browser_caps)
        read_caps = [item.name for item in browser_caps if item.category in {"browser_read", "browser_debug"}]
        write_caps = [item.name for item in browser_caps if item.category == "browser_write"]
        lines.extend([
            f"你当前可用的浏览器工具：{browser_names}。",
            "浏览器任务默认先读取再交互：优先用读取/判断类工具确认页面状态，再决定是否执行点击、输入、按键等写操作。",
            "如果需要浏览器会话，先调用 `browser_open` 获取 `session_id`，之后在同一任务中复用该 `session_id`，结束时优先调用 `browser_close` 释放会话。",
            "使用写操作前，应先确认目标元素存在或已可见；可优先组合 `browser_exists`、`browser_wait_for` 与读取类工具。",
            "不要把截图当默认输出；只有在需要视觉留痕、页面异常排查或文本不足以说明问题时才使用 `browser_screenshot`。",
            "浏览器工具的返回结果是事实来源。不要声称自己看到了工具未返回的页面内容。",
        ])
        if read_caps:
            lines.append(f"优先使用的浏览器读工具：{'、'.join(read_caps)}。")
        if write_caps:
            lines.append(f"高风险浏览器写工具：{'、'.join(write_caps)}；仅在有明确目标和依据时使用。")

    if non_browser_caps:
        lines.append("当前其他可用工具：" + "、".join(item.name for item in non_browser_caps) + "。")

    lines.append("如果工具调用失败，要基于错误信息调整下一步，而不是重复同一个无效调用。")
    return "\n".join(lines)
