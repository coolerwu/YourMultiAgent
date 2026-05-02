"""
app/agent/task_planner.py

将 Coordinator 输出解析为 Workspace Task DAG，并提供旧顺序 Worker 的线性回退计划。
"""

from __future__ import annotations

import json

from server.domain.agent.agent_entity import AgentEntity
from server.domain.agent.run_entity import TaskEntity, validate_task_plan


def parse_task_plan(plan_text: str, workers: list[AgentEntity]) -> list[TaskEntity]:
    """从 Coordinator 文本中解析任务计划；无法解析时回退为线性 Worker DAG。"""
    parsed = _extract_json_object(plan_text)
    tasks = _tasks_from_payload(parsed, workers) if parsed else []
    if not tasks:
        tasks = build_linear_task_plan(plan_text, workers)
    validate_task_plan(tasks, {worker.id for worker in workers})
    return tasks


def build_linear_task_plan(plan_text: str, workers: list[AgentEntity]) -> list[TaskEntity]:
    """兼容旧顺序模型：按 Worker order 构造线性 DAG。"""
    tasks: list[TaskEntity] = []
    previous_id = ""
    for index, worker in enumerate(_ordered_workers(workers), start=1):
        task_id = f"task-{index}"
        instruction = (
            "请根据主控拆解，仅完成分派给你的部分。\n\n"
            f"主控拆解：\n{plan_text.strip() or '请根据你的角色独立完成任务。'}"
        )
        tasks.append(
            TaskEntity(
                id=task_id,
                worker_id=worker.id,
                instruction=instruction,
                dependencies=[previous_id] if previous_id else [],
                expected_output="完成该 Worker 角色负责的可交付结果。",
            )
        )
        previous_id = task_id
    return tasks


def _tasks_from_payload(payload: dict, workers: list[AgentEntity]) -> list[TaskEntity]:
    raw_tasks = payload.get("tasks", [])
    if not isinstance(raw_tasks, list):
        return []
    worker_by_id = {worker.id: worker for worker in workers}
    worker_id_by_name = {worker.name: worker.id for worker in workers}
    tasks: list[TaskEntity] = []
    used_ids: set[str] = set()
    for index, item in enumerate(raw_tasks, start=1):
        if not isinstance(item, dict):
            continue
        worker_id = str(item.get("worker_id", "") or item.get("worker", "")).strip()
        if worker_id not in worker_by_id:
            worker_id = worker_id_by_name.get(worker_id, worker_id)
        instruction = str(item.get("instruction", "") or item.get("task", "") or item.get("description", "")).strip()
        task_id = str(item.get("id", "") or f"task-{index}").strip()
        if not task_id or task_id in used_ids:
            task_id = f"task-{index}"
        used_ids.add(task_id)
        dependencies = [
            str(dep).strip()
            for dep in item.get("dependencies", item.get("depends_on", []))
            if str(dep).strip()
        ]
        tasks.append(
            TaskEntity(
                id=task_id,
                worker_id=worker_id,
                instruction=instruction,
                dependencies=dependencies,
                expected_output=str(item.get("expected_output", "")).strip(),
            )
        )
    return tasks


def _extract_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            stripped = "\n".join(lines[1:-1]).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(stripped[start:end + 1])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


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
