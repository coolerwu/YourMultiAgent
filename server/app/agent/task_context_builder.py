"""
app/agent/task_context_builder.py

构造 Worker 执行单个 Task 时的上下文输入。
"""

from __future__ import annotations

from server.domain.agent.run_entity import TaskEntity


def build_task_assignment(
    *,
    user_message: str,
    plan_text: str,
    task: TaskEntity,
    completed_tasks: list[TaskEntity],
) -> str:
    upstream = [item for item in completed_tasks if item.id in set(task.dependencies)]
    upstream_text = "\n".join(
        f"- {item.id}: {item.result[:800] or '无输出'}"
        for item in upstream
    ) or "无"
    expected = task.expected_output.strip() or "完成该任务所需的明确结论或交付物。"
    return (
        f"原始用户目标：{user_message}\n\n"
        f"主控整体计划：\n{plan_text or '无'}\n\n"
        f"当前任务 ID：{task.id}\n"
        f"当前任务说明：\n{task.instruction}\n\n"
        f"上游任务结果：\n{upstream_text}\n\n"
        f"期望输出：{expected}\n\n"
        "请只完成当前任务，不要越权执行其他 Worker 的任务。"
        "如产出交付物，请写入当前 Workspace 的 `shared/` 目录或你的工作子目录，并在回答中明确路径。"
    )
