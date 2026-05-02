"""
app/agent/task_scheduler.py

Workspace Task DAG 的就绪任务选择与完成判断。
"""

from __future__ import annotations

from server.domain.agent.run_entity import TASK_STATUS_PENDING, TASK_STATUS_SUCCEEDED, TaskEntity


def next_ready_tasks(tasks: list[TaskEntity]) -> list[TaskEntity]:
    """返回当前依赖已满足、尚未执行的任务。"""
    succeeded = {task.id for task in tasks if task.status == TASK_STATUS_SUCCEEDED}
    return [
        task
        for task in tasks
        if task.status == TASK_STATUS_PENDING and all(dependency in succeeded for dependency in task.dependencies)
    ]


def all_tasks_finished(tasks: list[TaskEntity]) -> bool:
    return all(task.status != TASK_STATUS_PENDING and task.status != "running" for task in tasks)
