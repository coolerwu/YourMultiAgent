"""
app/agent/agent_app_service.py

Agent 应用服务：编排 Command/Query，协调 domain 与 infra。
不包含业务规则，只做流程编排。
新增：以 Workspace 为唯一编排入口运行 Coordinator + Workers；保留 Prompt 优化能力。
"""

import json
from typing import AsyncGenerator, Optional

from server.app.agent.command.generate_worker_cmd import GenerateWorkerCmd
from server.app.agent.command.optimize_prompt_cmd import OptimizePromptCmd
from server.domain.agent.entity.agent_entity import AgentEntity, ChatSessionEntity
from server.domain.agent.gateway.llm_gateway import LLMGateway
from server.domain.agent.gateway.workspace_gateway import WorkspaceGateway
from server.domain.agent.service.orchestrator import AgentOrchestrator
from server.domain.agent.service.session_history import (
    append_session_message,
    build_compact_source,
    build_session_title,
    create_session,
    needs_compact,
    refresh_session_memory,
    refresh_session_summary,
    summarize_memory,
)
from langchain_core.messages import HumanMessage, SystemMessage


class AgentAppService:
    def __init__(
        self,
        orchestrator: AgentOrchestrator,
        llm_gateway: LLMGateway,
        ws_gateway: Optional[WorkspaceGateway] = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._llm_gateway = llm_gateway
        self._ws_gateway = ws_gateway

    # ── Commands ──────────────────────────────────────────────

    async def run_workspace(
        self,
        workspace_id: str,
        user_message: str,
        session_id: str = "",
    ) -> AsyncGenerator[dict, None]:
        if self._ws_gateway is None:
            raise ValueError("WorkspaceGateway 未配置")
        workspace = await self._ws_gateway.find_by_id(workspace_id)
        if workspace is None:
            raise ValueError(f"Workspace 不存在: {workspace_id}")

        session = _find_session(workspace.sessions, session_id)
        created = False
        if session is None:
            session = create_session(user_message)
            workspace.sessions.insert(0, session)
            created = True
            await self._ws_gateway.save(workspace)
            yield {
                "type": "session_created",
                "session_id": session.id,
                "title": session.title,
            }

        session.title = session.title or build_session_title(user_message)
        session.status = "running"
        append_session_message(session, role="user", kind="user", content=user_message)
        await self._ws_gateway.save(workspace)
        text_buffers: dict[str, dict[str, str]] = {}
        pending_done: dict | None = None

        try:
            async for chunk in self._orchestrator.run(workspace, user_message, session):
                chunk_type = chunk.get("type")
                if chunk_type == "done":
                    pending_done = chunk
                    continue
                if chunk_type == "text":
                    key = chunk.get("node") or chunk.get("actor_id") or "assistant"
                    buffer = text_buffers.setdefault(
                        key,
                        {
                            "content": "",
                            "actor_id": chunk.get("actor_id", ""),
                            "actor_name": chunk.get("actor_name", ""),
                            "node": chunk.get("node", ""),
                        },
                    )
                    buffer["content"] += chunk.get("content", "")
                elif chunk_type in {"coordinator_end", "worker_end"}:
                    key = chunk.get("node") or chunk.get("actor_id") or "assistant"
                    buffer = text_buffers.pop(key, None)
                    if buffer and buffer["content"].strip():
                        append_session_message(
                            session,
                            role="assistant",
                            kind="assistant",
                            content=buffer["content"],
                            actor_id=buffer["actor_id"],
                            actor_name=buffer["actor_name"],
                            node=buffer["node"],
                        )
                elif chunk_type == "run_summary":
                    append_session_message(
                        session,
                        role="assistant",
                        kind="summary",
                        content=chunk.get("summary", ""),
                        actor_id=chunk.get("actor_id", ""),
                        actor_name=chunk.get("actor_name", ""),
                        node=chunk.get("node", ""),
                    )
                elif chunk_type in {"plan_created", "task_assigned", "worker_result", "tool_start", "tool_end"}:
                    append_session_message(
                        session,
                        role="event",
                        kind=chunk_type,
                        content=_event_to_content(chunk),
                        actor_id=chunk.get("actor_id", ""),
                        actor_name=chunk.get("actor_name", ""),
                        node=chunk.get("node", ""),
                    )
                yield chunk

            session.status = "idle"
        except Exception:
            session.status = "failed"
            await self._ws_gateway.save(workspace)
            raise

        for buffer in text_buffers.values():
            if buffer["content"].strip():
                append_session_message(
                    session,
                    role="assistant",
                    kind="assistant",
                    content=buffer["content"],
                    actor_id=buffer["actor_id"],
                    actor_name=buffer["actor_name"],
                    node=buffer["node"],
                )

        await self._refresh_session_summary(workspace, session)
        refresh_session_memory(session)
        await self._ws_gateway.save(workspace)
        yield {
            "type": "session_updated",
            "session_id": session.id,
            "summary": session.summary,
            "memory_items": summarize_memory(session.memory_items),
            "message_count": session.message_count,
            "created": created,
        }
        if pending_done is not None:
            yield pending_done

    async def optimize_prompt(self, cmd: OptimizePromptCmd) -> dict[str, str]:
        workspace = None
        if cmd.workspace_id and self._ws_gateway:
            workspace = await self._ws_gateway.find_by_id(cmd.workspace_id)

        agent = AgentEntity(
            id="prompt_optimizer",
            name=cmd.name or "未命名 Agent",
            provider=cmd.provider,
            model=cmd.model,
            system_prompt=cmd.system_prompt,
            temperature=cmd.temperature,
            max_tokens=cmd.max_tokens,
            tools=cmd.tools,
            llm_profile_id=cmd.llm_profile_id,
            codex_connection_id=cmd.codex_connection_id,
            base_url=cmd.base_url,
            api_key=cmd.api_key,
        )
        llm = self._llm_gateway.build(agent, workspace)
        response = await llm.ainvoke([
            SystemMessage(content=_PROMPT_OPTIMIZER_SYSTEM),
            HumanMessage(content=_build_optimize_request(cmd)),
        ])
        return _parse_optimize_response(response.content)

    async def generate_worker(self, cmd: GenerateWorkerCmd) -> dict:
        workspace = None
        if cmd.workspace_id and self._ws_gateway:
            workspace = await self._ws_gateway.find_by_id(cmd.workspace_id)

        agent = AgentEntity(
            id="worker_generator",
            name="Worker Generator",
            provider=cmd.provider,
            model=cmd.model,
            system_prompt="你负责生成 Worker 配置草稿。",
            llm_profile_id=cmd.llm_profile_id,
            codex_connection_id=cmd.codex_connection_id,
            base_url=cmd.base_url,
            api_key=cmd.api_key,
        )
        llm = self._llm_gateway.build(agent, workspace)
        response = await llm.ainvoke([
            SystemMessage(content=_WORKER_GENERATOR_SYSTEM),
            HumanMessage(content=_build_generate_worker_request(cmd)),
        ])
        return _parse_worker_response(response.content, cmd)

    async def _refresh_session_summary(self, workspace, session: ChatSessionEntity) -> None:
        if not needs_compact(session):
            return
        try:
            summary = await _summarize_session_with_llm(self._llm_gateway, workspace, session)
            if summary.strip():
                session.summary = summary.strip()
                if session.messages:
                    session.updated_at = session.messages[-1].created_at
                return
        except Exception:
            pass
        refresh_session_summary(session)

_PROMPT_OPTIMIZER_SYSTEM = """你是资深 AI Agent Prompt 设计师。
你的任务是优化多 Agent 协作中的提示词，使其更清晰、可执行、边界更明确。

必须遵守：
1. 保留原任务意图，不要改掉 Agent 的核心职责。
2. 输出中文。
3. 只返回 JSON，不要输出 Markdown 或解释性前缀。
4. JSON 结构固定为：
{"optimized_prompt":"优化后的 Prompt","reason":"1-2 句简短说明"}
"""


def _build_optimize_request(cmd: OptimizePromptCmd) -> str:
    tools_text = "、".join(cmd.tools) if cmd.tools else "无"
    current_prompt = cmd.system_prompt.strip()

    if cmd.prompt_kind == "edge_prompt":
        goal = cmd.goal or "润色当前连线 Prompt，让它更适合作为上下游节点之间的补充指令"
        if not current_prompt:
            current_prompt = "当前连线 Prompt 为空，请生成一条简洁明确的下游补充指令。"
        return (
            f"Prompt 类型：连线 Prompt\n"
            f"上游节点：{cmd.source_name or '未命名上游 Agent'}\n"
            f"下游节点：{cmd.target_name or '未命名下游 Agent'}\n"
            f"触发文件：{cmd.artifact or '无，默认边'}\n"
            f"优化目标：{goal}\n"
            f"当前连线 Prompt：\n{current_prompt}"
        )

    goal = cmd.goal or "润色当前 Prompt，让它更清晰、更稳定、更适合执行"
    if not current_prompt:
        current_prompt = "当前 Prompt 为空，请基于 Agent 名称和工具生成一个首版 Prompt。"
    return (
        f"Prompt 类型：System Prompt\n"
        f"Agent 名称：{cmd.name or '未命名 Agent'}\n"
        f"优化目标：{goal}\n"
        f"可用工具：{tools_text}\n"
        f"当前 System Prompt：\n{current_prompt}"
    )


def _parse_optimize_response(content: object) -> dict[str, str]:
    text = content if isinstance(content, str) else str(content)
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and start < end:
        text = text[start:end + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {
            "optimized_prompt": text,
            "reason": "模型未返回标准 JSON，已按纯文本结果回退。",
        }

    optimized_prompt = str(data.get("optimized_prompt", "")).strip()
    reason = str(data.get("reason", "")).strip()
    return {
        "optimized_prompt": optimized_prompt or text,
        "reason": reason or "已基于当前 Agent 配置生成优化建议。",
    }


_WORKER_GENERATOR_SYSTEM = """你是资深多智能体系统设计师。
你的任务是根据用户目标，为当前 Workspace 生成多个合适的 Worker 草稿配置。

必须遵守：
1. 输出中文。
2. 只返回 JSON，不要输出 Markdown 或解释性前缀。
3. JSON 结构固定为：
{"workers":[{"name":"Worker 名称","system_prompt":"完整 Worker Prompt","work_subdir":"建议目录","tools":["tool1"]}],"reason":"1-2 句说明"}
4. tools 只能从给定的可用工具列表中选择。
5. 不要生成与已有 Worker 重名的角色。
6. system_prompt 里要包含职责边界、共享交付和越权限制，但不要复述用户原话。
7. 你要自行判断需要几个 Worker，优先最少必要分工；任务简单时不要硬拆太多角色，但不要返回空数组。
"""

_SESSION_COMPACTOR_SYSTEM = """你负责把长会话压缩成可继续工作的结构化摘要。

必须遵守：
1. 输出中文。
2. 不要复述噪声过程，只保留后续执行真正需要的信息。
3. 输出严格使用以下五段标题，顺序不能变：
【用户目标】
【已完成】
【关键约束】
【重要文件】
【待继续】
4. 每段只写高价值要点；没有内容时写“无”。
5. 不要输出 Markdown 代码块，不要解释你的做法。
"""


def _build_generate_worker_request(cmd: GenerateWorkerCmd) -> str:
    return (
        f"用户希望新增的 Worker：{cmd.user_goal or '未说明'}\n"
        f"主控智能体名称：{cmd.coordinator_name or '主控智能体'}\n"
        f"主控智能体 Prompt：\n{cmd.coordinator_prompt or '无'}\n\n"
        f"已有 Worker：{'、'.join(cmd.existing_worker_names) if cmd.existing_worker_names else '无'}\n"
        f"可用工具：{'、'.join(cmd.available_tools) if cmd.available_tools else '无'}\n"
        "请自行判断需要几个 Worker，并生成一组适合被主控智能体调度的 Worker 草稿，覆盖这个目标所需的关键角色分工。"
    )


def _build_compact_request(session: ChatSessionEntity) -> str:
    return (
        "请压缩以下历史会话，生成便于后续续聊的结构化摘要。\n\n"
        f"{build_compact_source(session)}"
    )


def _parse_worker_response(content: object, cmd: GenerateWorkerCmd) -> dict:
    text = content if isinstance(content, str) else str(content)
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and start < end:
        text = text[start:end + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {}

    raw_workers = data.get("workers", [])
    if not isinstance(raw_workers, list) or not raw_workers:
        raw_workers = [data] if isinstance(data, dict) else []

    existing_names = {name.strip() for name in cmd.existing_worker_names if name.strip()}
    generated_names: set[str] = set()
    workers = []
    for item in raw_workers:
        if not isinstance(item, dict):
            continue
        parsed = _normalize_worker_item(item, cmd)
        name = parsed["name"]
        if name in existing_names or name in generated_names:
            continue
        generated_names.add(name)
        workers.append(parsed)

    if not workers:
        workers = [_normalize_worker_item({}, cmd)]

    return {
        "workers": workers,
        "reason": str(data.get("reason", "")).strip() or f"已根据当前 Workspace 生成 {len(workers)} 个 Worker 草稿。",
    }


def _normalize_worker_item(data: dict, cmd: GenerateWorkerCmd) -> dict:
    allowed_tools = set(cmd.available_tools)
    tools = [tool for tool in data.get("tools", []) if tool in allowed_tools]
    name = str(data.get("name", "")).strip() or "新 Worker"
    work_subdir = str(data.get("work_subdir", "")).strip() or _default_worker_subdir(name)
    return {
        "id": "",
        "name": name,
        "provider": cmd.provider,
        "model": cmd.model,
        "system_prompt": str(data.get("system_prompt", "")).strip() or (
            "你是当前 Worker，请只完成分配给你的子任务。"
        ),
        "temperature": 0.7,
        "max_tokens": 4096,
        "tools": tools,
        "llm_profile_id": cmd.llm_profile_id,
        "base_url": cmd.base_url,
        "api_key": cmd.api_key,
        "work_subdir": work_subdir,
    }


def _default_worker_subdir(name: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    return safe or "worker"


async def _summarize_session_with_llm(
    llm_gateway: LLMGateway,
    workspace,
    session: ChatSessionEntity,
) -> str:
    if workspace.coordinator is not None:
        base_agent = workspace.coordinator
    else:
        base_agent = AgentEntity(
            id="session_compactor",
            name="Session Compactor",
            provider=workspace.default_provider,
            model=workspace.default_model,
            system_prompt=_SESSION_COMPACTOR_SYSTEM,
            temperature=0.1,
            max_tokens=1200,
        )

    summarizer = AgentEntity(
        id="session_compactor",
        name="Session Compactor",
        provider=base_agent.provider,
        model=base_agent.model,
        system_prompt=_SESSION_COMPACTOR_SYSTEM,
        temperature=0.1,
        max_tokens=1200,
        llm_profile_id=base_agent.llm_profile_id,
        base_url=base_agent.base_url,
        api_key=base_agent.api_key,
    )
    llm = llm_gateway.build(summarizer, workspace)
    response = await llm.ainvoke([
        SystemMessage(content=_SESSION_COMPACTOR_SYSTEM),
        HumanMessage(content=_build_compact_request(session)),
    ])
    text = response.content if isinstance(response.content, str) else str(response.content)
    return text.strip()


def _find_session(sessions: list[ChatSessionEntity], session_id: str) -> ChatSessionEntity | None:
    if not session_id:
        return None
    return next((item for item in sessions if item.id == session_id), None)


def _event_to_content(event: dict) -> str:
    event_type = event.get("type", "")
    if event_type == "plan_created":
        return f"{event.get('coordinator_name', '主控智能体')} 开始拆解任务"
    if event_type == "task_assigned":
        return f"已分派给 {event.get('worker_name', '')}：{event.get('assignment', '')}"
    if event_type == "worker_result":
        return f"{event.get('worker_name', '')} 已交付结果：{event.get('summary', '')}"
    if event_type == "tool_start":
        return f"调用工具 {event.get('tool', '')}"
    if event_type == "tool_end":
        return f"工具 {event.get('tool', '')} 返回：{event.get('result', '')}"
    return str(event)
