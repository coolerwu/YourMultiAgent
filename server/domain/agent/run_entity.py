"""
domain/agent/run_entity.py

Workspace Run / Task / Artifact 领域模型与 DAG 计划校验规则。
"""

from __future__ import annotations

from dataclasses import dataclass, field


RUN_STATUS_RUNNING = "running"
RUN_STATUS_SUCCEEDED = "succeeded"
RUN_STATUS_FAILED = "failed"

TASK_STATUS_PENDING = "pending"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_SUCCEEDED = "succeeded"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_SKIPPED = "skipped"


@dataclass
class ArtifactEntity:
    """Worker 交付物引用。"""

    path: str
    task_id: str
    worker_id: str
    description: str = ""
    created_at: str = ""


@dataclass
class TaskEntity:
    """Coordinator 拆出的单个可执行任务。"""

    id: str
    worker_id: str
    instruction: str
    dependencies: list[str] = field(default_factory=list)
    status: str = TASK_STATUS_PENDING
    result: str = ""
    expected_output: str = ""
    error: str = ""
    artifacts: list[ArtifactEntity] = field(default_factory=list)


@dataclass
class RunEntity:
    """一次用户目标执行。"""

    id: str
    status: str
    user_message: str
    plan_text: str = ""
    tasks: list[TaskEntity] = field(default_factory=list)
    artifacts: list[ArtifactEntity] = field(default_factory=list)
    summary: str = ""
    error: str = ""
    created_at: str = ""
    updated_at: str = ""


def validate_task_plan(tasks: list[TaskEntity], worker_ids: set[str]) -> None:
    """校验任务计划的 Worker 引用、依赖引用和环路。"""
    if not tasks:
        raise ValueError("任务计划不能为空")

    task_ids: set[str] = set()
    for task in tasks:
        if not task.id.strip():
            raise ValueError("任务 id 不能为空")
        if task.id in task_ids:
            raise ValueError(f"任务 id 重复: {task.id}")
        task_ids.add(task.id)
        if task.worker_id not in worker_ids:
            raise ValueError(f"任务 {task.id} 引用了不存在的 Worker: {task.worker_id}")
        if not task.instruction.strip():
            raise ValueError(f"任务 {task.id} 的 instruction 不能为空")

    for task in tasks:
        for dependency in task.dependencies:
            if dependency not in task_ids:
                raise ValueError(f"任务 {task.id} 引用了不存在的依赖任务: {dependency}")

    _validate_acyclic(tasks)


def _validate_acyclic(tasks: list[TaskEntity]) -> None:
    graph = {task.id: list(task.dependencies) for task in tasks}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            raise ValueError(f"任务依赖存在环路: {task_id}")
        visiting.add(task_id)
        for dependency in graph.get(task_id, []):
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for item in graph:
        visit(item)
