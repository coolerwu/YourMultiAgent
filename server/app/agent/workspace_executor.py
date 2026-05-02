"""
app/agent/workspace_executor.py

Workspace 单编排执行器：
- 先运行 Coordinator 生成任务计划
- 再按任务依赖调度 Worker
- 共享交接物约定写入 Workspace 根目录下的 shared/

位于 app 层，负责运行流程编排，不承载纯领域规则定义。
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from server.app.agent.task_context_builder import build_task_assignment
from server.app.agent.task_planner import parse_task_plan
from server.app.agent.task_scheduler import next_ready_tasks
from server.domain.agent.agent_entity import AgentEntity, ChatSessionEntity, WorkspaceEntity, WorkspaceKind
from server.domain.agent.llm_gateway import LLMGateway
from server.domain.agent.agent_runtime import AgentRuntime
from server.domain.agent.run_entity import (
    RUN_STATUS_FAILED,
    RUN_STATUS_RUNNING,
    RUN_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    ArtifactEntity,
    RunEntity,
    TaskEntity,
)
from server.domain.agent.session_history import build_runtime_messages, now_iso
from server.domain.worker.capability_entity import CapabilityEntity
from server.domain.worker.worker_gateway import WorkerGateway
from server.support.app_logging import get_logger, log_context, log_event

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
        with log_context(workspace_id=self._workspace.id, session_id=session.id):
            try:
                root = Path(self._workspace_root)
                root.mkdir(parents=True, exist_ok=True)
                (root / "shared").mkdir(parents=True, exist_ok=True)
                log_event(
                    logger,
                    event="workspace_run_started",
                    layer="agent",
                    action="workspace_run",
                    status="started",
                    extra={"workspace_kind": self._workspace.kind, "workspace_root": str(root)},
                )

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
                    log_event(logger, event="workspace_run_finished", layer="agent", action="workspace_run", status="success")
                    yield {"type": "done"}
                    return

                coordinator = self._workspace.coordinator
                if coordinator is None:
                    raise ValueError("Workspace 尚未配置主控智能体")

                run = _create_run(user_message)
                session.runs.insert(0, run)
                yield {
                    "type": "run_started",
                    "run_id": run.id,
                    "status": run.status,
                    "user_message": user_message,
                    "actor_id": coordinator.id,
                    "actor_name": coordinator.name,
                    "actor_kind": "coordinator",
                }
                yield {
                    "type": "plan_created",
                    "run_id": run.id,
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
                run.plan_text = plan_text
                if not self._workspace.workers:
                    run.status = RUN_STATUS_SUCCEEDED
                    run.summary = plan_text
                    run.updated_at = now_iso()
                    yield {
                        "type": "run_summary",
                        "run_id": run.id,
                        "actor_id": coordinator.id,
                        "actor_name": coordinator.name,
                        "actor_kind": "coordinator",
                        "summary": run.summary,
                    }
                    yield {
                        "type": "run_finished",
                        "run_id": run.id,
                        "status": run.status,
                        "summary": run.summary,
                        "actor_id": coordinator.id,
                        "actor_name": coordinator.name,
                        "actor_kind": "coordinator",
                    }
                    log_event(logger, event="workspace_run_finished", layer="agent", action="workspace_run", status="success")
                    yield {"type": "done"}
                    return
                run.tasks = parse_task_plan(plan_text, self._workspace.workers)
                run.updated_at = now_iso()

                yield {
                    "type": "plan_created",
                    "run_id": run.id,
                    "coordinator": coordinator.id,
                    "coordinator_name": coordinator.name,
                    "tasks": [_task_event_payload(task, self._workspace.workers) for task in run.tasks],
                    "edges": [
                        {"from": dependency, "to": task.id}
                        for task in run.tasks
                        for dependency in task.dependencies
                    ],
                }

                worker_outputs: list[dict[str, str]] = []
                while True:
                    ready_tasks = next_ready_tasks(run.tasks)
                    if not ready_tasks:
                        unfinished = [task.id for task in run.tasks if task.status not in {TASK_STATUS_SUCCEEDED, TASK_STATUS_FAILED}]
                        if unfinished:
                            raise ValueError(f"任务依赖无法继续调度: {', '.join(unfinished)}")
                        break
                    task = ready_tasks[0]
                    worker = _find_worker(self._workspace.workers, task.worker_id)
                    if worker is None:
                        raise ValueError(f"任务 {task.id} 引用了不存在的 Worker: {task.worker_id}")
                    assignment = build_task_assignment(
                        user_message=user_message,
                        plan_text=plan_text,
                        task=task,
                        completed_tasks=[item for item in run.tasks if item.status == TASK_STATUS_SUCCEEDED],
                    )
                    task.status = TASK_STATUS_RUNNING
                    run.updated_at = now_iso()
                    log_event(
                        logger,
                        event="task_assignment_created",
                        layer="agent",
                        action="assign_task",
                        status="success",
                        worker_id=worker.id,
                        extra={"worker_name": worker.name, "task_id": task.id},
                    )
                    yield {
                        "type": "task_started",
                        "run_id": run.id,
                        "task_id": task.id,
                        "worker": worker.id,
                        "worker_id": worker.id,
                        "worker_name": worker.name,
                        "instruction": task.instruction,
                        "dependencies": list(task.dependencies),
                        "actor_id": worker.id,
                        "actor_name": worker.name,
                        "actor_kind": "worker",
                    }
                    yield {
                        "type": "task_assigned",
                        "run_id": run.id,
                        "task_id": task.id,
                        "worker": worker.id,
                        "worker_name": worker.name,
                        "actor_id": coordinator.id,
                        "actor_name": coordinator.name,
                        "actor_kind": "coordinator",
                        "assignment": assignment,
                    }
                    output = ""
                    try:
                        async for event in self._stream_agent(
                            agent=worker,
                            event_type_prefix="worker",
                            session=session,
                            user_message=assignment,
                        ):
                            if event.get("type") == "text" and event.get("node") == worker.id:
                                output += event.get("content", "")
                            yield event
                    except Exception as exc:
                        task.status = TASK_STATUS_FAILED
                        task.error = str(exc)
                        run.status = RUN_STATUS_FAILED
                        run.error = str(exc)
                        run.updated_at = now_iso()
                        yield {
                            "type": "task_failed",
                            "run_id": run.id,
                            "task_id": task.id,
                            "worker": worker.id,
                            "worker_id": worker.id,
                            "worker_name": worker.name,
                            "error": str(exc),
                            "actor_id": worker.id,
                            "actor_name": worker.name,
                            "actor_kind": "worker",
                        }
                        raise
                    task.status = TASK_STATUS_SUCCEEDED
                    task.result = output
                    task.artifacts = _extract_artifacts(output, task, worker)
                    run.artifacts.extend(task.artifacts)
                    run.updated_at = now_iso()
                    worker_outputs.append({"worker_name": worker.name, "output": output})
                    for artifact in task.artifacts:
                        yield {
                            "type": "artifact_recorded",
                            "run_id": run.id,
                            "task_id": task.id,
                            "worker": worker.id,
                            "worker_id": worker.id,
                            "worker_name": worker.name,
                            "path": artifact.path,
                            "description": artifact.description,
                            "actor_id": worker.id,
                            "actor_name": worker.name,
                            "actor_kind": "worker",
                        }
                    yield {
                        "type": "task_finished",
                        "run_id": run.id,
                        "task_id": task.id,
                        "worker": worker.id,
                        "worker_id": worker.id,
                        "worker_name": worker.name,
                        "summary": output[:240],
                        "artifacts": [
                            {"path": artifact.path, "description": artifact.description}
                            for artifact in task.artifacts
                        ],
                        "actor_id": worker.id,
                        "actor_name": worker.name,
                        "actor_kind": "worker",
                    }
                    yield {
                        "type": "worker_result",
                        "run_id": run.id,
                        "task_id": task.id,
                        "worker": worker.id,
                        "worker_name": worker.name,
                        "actor_id": worker.id,
                        "actor_name": worker.name,
                        "actor_kind": "worker",
                        "summary": output[:240],
                    }

                run.status = RUN_STATUS_SUCCEEDED
                run.summary = _build_run_summary(plan_text, worker_outputs)
                run.updated_at = now_iso()
                yield {
                    "type": "run_summary",
                    "run_id": run.id,
                    "actor_id": coordinator.id,
                    "actor_name": coordinator.name,
                    "actor_kind": "coordinator",
                    "summary": run.summary,
                }
                yield {
                    "type": "run_finished",
                    "run_id": run.id,
                    "status": run.status,
                    "summary": run.summary,
                    "actor_id": coordinator.id,
                    "actor_name": coordinator.name,
                    "actor_kind": "coordinator",
                }
                log_event(logger, event="workspace_run_finished", layer="agent", action="workspace_run", status="success")
                yield {"type": "done"}
            except Exception as exc:
                for run in session.runs:
                    if run.status == RUN_STATUS_RUNNING:
                        run.status = RUN_STATUS_FAILED
                        run.error = str(exc)
                        run.updated_at = now_iso()
                        break
                log_event(
                    logger,
                    event="workspace_run_failed",
                    layer="agent",
                    action="workspace_run",
                    status="error",
                    level=40,
                    extra={"error": str(exc)},
                )
                raise

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

        with log_context(node_id=agent.id, agent_name=agent.name):
            try:
                yield {
                    "type": f"{event_type_prefix}_start",
                    "node": agent.id,
                    "node_name": agent.name,
                    "actor_id": agent.id,
                    "actor_name": agent.name,
                    "actor_kind": event_type_prefix,
                }
                log_event(
                    logger,
                    event="agent_run_started",
                    layer="agent",
                    action="agent_run",
                    status="started",
                    provider=str(agent.provider),
                    model=agent.model,
                )
                runtime = AgentRuntime(
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
                log_event(
                    logger,
                    event="agent_run_context",
                    layer="agent",
                    action="agent_run",
                    status="success",
                    provider=str(agent.provider),
                    model=agent.model,
                    extra={
                        "runtime_message_count": len(runtime_messages),
                        "user_message_chars": len(user_message or ""),
                        "tool_count": len(tools),
                        "work_dir": work_dir,
                    },
                )
                async for event in runtime.run([
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
                log_event(
                    logger,
                    event="agent_run_finished",
                    layer="agent",
                    action="agent_run",
                    status="success",
                    provider=str(agent.provider),
                    model=agent.model,
                )
                yield {
                    "type": f"{event_type_prefix}_end",
                    "node": agent.id,
                    "node_name": agent.name,
                    "actor_id": agent.id,
                    "actor_name": agent.name,
                    "actor_kind": event_type_prefix,
                }
            except Exception as exc:
                log_event(
                    logger,
                    event="agent_run_failed",
                    layer="agent",
                    action="agent_run",
                    status="error",
                    level=40,
                    provider=str(agent.provider),
                    model=agent.model,
                    extra={"error": str(exc)},
                )
                raise


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


def _create_run(user_message: str) -> RunEntity:
    timestamp = now_iso()
    return RunEntity(
        id=str(uuid.uuid4()),
        status=RUN_STATUS_RUNNING,
        user_message=user_message,
        created_at=timestamp,
        updated_at=timestamp,
    )


def _find_worker(workers: list[AgentEntity], worker_id: str) -> AgentEntity | None:
    return next((worker for worker in workers if worker.id == worker_id), None)


def _task_event_payload(task: TaskEntity, workers: list[AgentEntity]) -> dict:
    worker = _find_worker(workers, task.worker_id)
    return {
        "id": task.id,
        "worker_id": task.worker_id,
        "worker_name": worker.name if worker else task.worker_id,
        "instruction": task.instruction,
        "dependencies": list(task.dependencies),
        "status": task.status,
        "expected_output": task.expected_output,
    }


def _extract_artifacts(output: str, task: TaskEntity, worker: AgentEntity) -> list[ArtifactEntity]:
    artifacts: list[ArtifactEntity] = []
    seen: set[str] = set()
    for match in re.findall(r"(?:`([^`]+)`|([A-Za-z0-9_./-]+\.[A-Za-z0-9]+))", output):
        path = next((item for item in match if item), "").strip()
        if not path or path in seen:
            continue
        if "/" not in path and "." not in path:
            continue
        seen.add(path)
        artifacts.append(
            ArtifactEntity(
                path=path,
                task_id=task.id,
                worker_id=worker.id,
                description=f"{worker.name} 输出中提到的交付物",
                created_at=now_iso(),
            )
        )
    return artifacts


def _build_coordinator_message(user_message: str, workers: list[AgentEntity]) -> str:
    worker_lines = "\n".join(
        f"- id={worker.id}; name={worker.name}; order={worker.order or index}; prompt={worker.system_prompt[:160]}"
        for index, worker in enumerate(_ordered_workers(workers), start=1)
    ) or "- 暂无 Worker"
    return (
        f"用户任务：{user_message}\n\n"
        f"可用 Worker：\n{worker_lines}\n\n"
        "请输出一个可执行任务计划。优先返回严格 JSON，不要使用 Markdown 代码块；结构如下：\n"
        '{"tasks":[{"id":"task-1","worker_id":"worker-id","instruction":"任务说明",'
        '"dependencies":[],"expected_output":"期望输出"}]}\n'
        "任务必须只引用可用 Worker 的 id，dependencies 必须引用同一 JSON 中已有任务 id。"
        "如果任务需要交接物，统一要求写入当前 Workspace 的 `shared/` 目录。"
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
