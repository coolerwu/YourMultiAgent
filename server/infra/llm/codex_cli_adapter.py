"""
infra/llm/codex_cli_adapter.py

将本机 Codex CLI 包装为可被当前 ReAct 循环消费的聊天模型适配器。
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from server.infra.codex.codex_cli import detect_codex_path


class CodexCLIAdapter:
    def __init__(
        self,
        model: str,
        codex_path: str = "",
        tools: list[dict] | None = None,
        work_dir: str = "",
    ) -> None:
        self._model = model or "gpt-5"
        self._codex_path = codex_path or detect_codex_path()
        self._tools = tools or []
        self._work_dir = work_dir

    def bind_tools(self, tools: list[dict]):
        return CodexCLIAdapter(
            model=self._model,
            codex_path=self._codex_path,
            tools=tools,
            work_dir=self._work_dir,
        )

    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        return await self._run(messages)

    async def astream(self, messages: list[Any]):
        yield await self._run(messages)

    async def _run(self, messages: list[Any]) -> AIMessage:
        if not self._codex_path:
            raise ValueError("未检测到本机 codex CLI")

        schema = _build_output_schema(bool(self._tools))
        prompt = _build_exec_prompt(messages, self._tools)

        with tempfile.TemporaryDirectory(prefix="yourmultiagent-codex-") as temp_dir:
            schema_path = Path(temp_dir) / "schema.json"
            output_path = Path(temp_dir) / "output.json"
            schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

            args = [
                self._codex_path,
                "exec",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--color",
                "never",
                "--output-schema",
                str(schema_path),
                "-o",
                str(output_path),
                "--model",
                self._model,
            ]
            if self._work_dir:
                args.extend(["-C", self._work_dir])
            args.append(prompt)

            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._work_dir or None,
                env=_build_codex_env(),
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                raise ValueError(_format_codex_error(stdout.decode("utf-8", errors="ignore"), stderr.decode("utf-8", errors="ignore")))
            if not output_path.exists():
                raise ValueError("Codex CLI 未生成最终输出")

            raw = output_path.read_text(encoding="utf-8").strip()
            if not raw:
                raise ValueError("Codex CLI 返回了空结果")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Codex CLI 返回了不可解析结果: {raw}") from exc

        return AIMessage(
            content=str(data.get("content", "")).strip(),
            tool_calls=_normalize_tool_calls(data.get("tool_calls", [])),
        )


def _build_output_schema(with_tools: bool) -> dict:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "content": {"type": "string"},
        },
        "required": ["content"],
    }
    if with_tools:
        schema["properties"]["tool_calls"] = {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "args": {"type": "object"},
                },
                "required": ["id", "name", "args"],
            },
        }
        schema["required"].append("tool_calls")
    return schema


def _build_exec_prompt(messages: list[Any], tools: list[dict]) -> str:
    lines = [
        "你是多 Agent 平台中的底层推理模型适配器。",
        "你只能基于提供的消息做推理，不要运行 shell 命令，不要读写文件，不要自行假设外部环境。",
        "你必须输出满足给定 JSON Schema 的最终结果。",
    ]
    if tools:
        lines.extend([
            "如果需要调用工具，请在 tool_calls 中返回待调用工具。",
            "tool_calls 中每个元素必须包含 id、name、args。",
            "如果不需要工具，返回空数组。",
            "只能从以下工具中选择：",
        ])
        for tool in tools:
            lines.append(f"- {tool.get('name')}: {tool.get('description', '')}")
    lines.append("")
    lines.append("对话消息如下：")
    for message in messages:
        lines.append(f"[{_role_name(message)}]")
        lines.append(_message_content(message))
        lines.append("")
    return "\n".join(lines).strip()


def _role_name(message: Any) -> str:
    if hasattr(message, "type"):
        return str(message.type)
    return message.__class__.__name__


def _message_content(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, list):
        return json.dumps(content, ensure_ascii=False)
    return str(content)


def _normalize_tool_calls(tool_calls: Any) -> list[dict]:
    normalized: list[dict] = []
    if not isinstance(tool_calls, list):
        return normalized
    for index, item in enumerate(tool_calls, start=1):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        args = item.get("args", {})
        if not name or not isinstance(args, dict):
            continue
        normalized.append({
            "id": str(item.get("id") or f"tool_call_{index}"),
            "name": name,
            "args": args,
        })
    return normalized


def _format_codex_error(stdout: str, stderr: str) -> str:
    parts = [part.strip() for part in [stdout, stderr] if part.strip()]
    if not parts:
        return "Codex CLI 执行失败"
    return "Codex CLI 执行失败：\n" + "\n".join(parts[-2:])


def _build_codex_env() -> dict[str, str]:
    env = dict(os.environ)
    env["OTEL_SDK_DISABLED"] = "true"

    # 避免服务进程里的空 OpenAI 认证变量污染 codex login 登录态。
    # Codex 走 ChatGPT 登录时，这些空值会让底层客户端错误地构造认证头。
    for key in [
        "OPENAI_API_KEY",
        "OPENAI_AUTH_TOKEN",
        "OPENAI_BASE_URL",
        "OPENAI_API_BASE",
        "OPENAI_ORG_ID",
        "OPENAI_ORGANIZATION",
        "OPENAI_PROJECT",
    ]:
        value = env.get(key)
        if value is not None and not str(value).strip():
            env.pop(key, None)

    return env
