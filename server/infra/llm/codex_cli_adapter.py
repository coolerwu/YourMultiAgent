"""
infra/llm/codex_cli_adapter.py

将本机 Codex CLI 包装为可被当前 ReAct 循环消费的聊天模型适配器。
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import tempfile
import time
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from server.infra.codex.codex_cli import build_codex_subprocess_env, detect_codex_path
from server.support.app_logging import get_logger


def _int_env(name: str, default: int) -> int:
    raw = (os.environ.get(name, "") or "").strip()
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


_CODEX_EXEC_TIMEOUT_SECONDS = _int_env("YOURMULTIAGENT_CODEX_EXEC_TIMEOUT_SECONDS", 300)
_CODEX_EXEC_MAX_ATTEMPTS = _int_env("YOURMULTIAGENT_CODEX_EXEC_MAX_ATTEMPTS", 2)
logger = get_logger(__name__)


class CodexCLIAdapter:
    def __init__(
        self,
        model: str,
        codex_path: str = "",
        tools: list[dict] | None = None,
        work_dir: str = "",
        simple_output_mode: bool = False,
    ) -> None:
        self._model = (model or "").strip()
        self._codex_path = codex_path or detect_codex_path()
        self._tools = tools or []
        self._work_dir = work_dir
        self._simple_output_mode = simple_output_mode

    def bind_tools(self, tools: list[dict]):
        return CodexCLIAdapter(
            model=self._model,
            codex_path=self._codex_path,
            tools=tools,
            work_dir=self._work_dir,
            simple_output_mode=self._simple_output_mode and not bool(tools),
        )

    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        return await self._run(messages)

    async def astream(self, messages: list[Any]):
        yield await self._run(messages)

    async def _run(self, messages: list[Any]) -> AIMessage:
        if not self._codex_path:
            raise ValueError("未检测到本机 codex CLI")

        structured_output = not self._simple_output_mode or bool(self._tools)
        prompt = _build_exec_prompt(messages, self._tools, structured_output=structured_output)
        args = [
            self._codex_path,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--color",
            "never",
        ]
        if self._model:
            args.extend(["--model", self._model])
        if self._work_dir:
            args.extend(["-C", self._work_dir])

        if not structured_output:
            args.append("-")  # 从 stdin 读取 prompt
            content = await _run_codex_simple_with_retry(args, prompt, self._work_dir or "")
            return AIMessage(content=content, tool_calls=[])

        schema = _build_output_schema(bool(self._tools))
        # 放在工作目录下，保证 read-only sandbox 也可写；目录名使用随机后缀避免并发冲突。
        work_dir_path = Path(self._work_dir) if self._work_dir else Path.cwd()
        work_dir_path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".yourmultiagent-codex-", dir=str(work_dir_path)) as temp_dir:
            schema_path = Path(temp_dir) / "schema.json"
            output_path = Path(temp_dir) / "output.json"
            schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
            args.extend([
                "--output-schema",
                str(schema_path),
                "-o",
                str(output_path),
                prompt,
            ])
            data = await _run_codex_exec_with_retry(args, output_path, self._work_dir or "")

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


def _build_exec_prompt(messages: list[Any], tools: list[dict], *, structured_output: bool) -> str:
    lines = [
        "你是多 Agent 平台中的底层推理模型适配器。",
        "你只能基于提供的消息做推理，不要运行 shell 命令，不要读写文件，不要自行假设外部环境。",
    ]
    if structured_output:
        lines.append("你必须输出满足给定 JSON Schema 的最终结果。")
    else:
        lines.append("请直接输出最终回答正文，不要添加额外的 JSON 包装。")

    if tools and structured_output:
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
    raw_message = "\n".join(parts[-2:]) if parts else ""
    known_message = _explain_known_codex_error(raw_message)
    if known_message:
        return known_message
    if not parts:
        return "Codex CLI 执行失败"
    return "Codex CLI 执行失败：\n" + raw_message


def _explain_known_codex_error(raw_message: str) -> str:
    lowered = raw_message.lower()
    if "could not resolve authentication method" in lowered:
        return (
            "Codex CLI 执行失败：检测到宿主环境里混入了额外的 OpenAI 鉴权配置，"
            "导致 ChatGPT 登录态与 API Key/Header 同时生效。当前版本会在下次执行时自动隔离这类环境变量；"
            "如果问题仍存在，请检查启动后端的 shell 是否额外注入了自定义 OpenAI 请求头。"
        )
    if "request not allowed" in lowered and "403" in lowered:
        return (
            "Codex CLI 执行失败：当前请求被 OpenAI 拒绝（403 Request not allowed）。"
            "这通常是因为 Codex 进程继承了错误的 OpenAI/Azure OpenAI 环境配置，或本机登录态本身无权访问当前请求。"
        )
    return ""


def _build_codex_env() -> dict[str, str]:
    env = build_codex_subprocess_env(os.environ)
    return env


async def _terminate_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    pid = getattr(process, "pid", None)
    if isinstance(pid, int) and pid > 0:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            process.kill()
    else:
        process.kill()
    try:
        await asyncio.wait_for(process.wait(), timeout=3)
    except asyncio.TimeoutError:
        pass


async def _run_codex_exec_with_retry(
    args: list[str],
    output_path: Path,
    work_dir: str,
) -> dict[str, Any]:
    attempts = max(1, _CODEX_EXEC_MAX_ATTEMPTS)
    for attempt in range(1, attempts + 1):
        process = None
        started_at = time.monotonic()
        try:
            if output_path.exists():
                output_path.unlink()
            logger.info(
                "codex_exec_start mode=structured attempt=%s/%s timeout=%ss work_dir=%s arg_count=%s",
                attempt,
                attempts,
                _CODEX_EXEC_TIMEOUT_SECONDS,
                work_dir,
                len(args),
            )
            process = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir or None,
                env=_build_codex_env(),
                start_new_session=True,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=_CODEX_EXEC_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "codex_exec_timeout mode=structured attempt=%s/%s pid=%s elapsed_ms=%s",
                    attempt,
                    attempts,
                    getattr(process, "pid", 0),
                    int((time.monotonic() - started_at) * 1000),
                )
                await _terminate_process(process)
                if attempt < attempts:
                    continue
                raise ValueError(
                    f"Codex CLI 执行超时（>{_CODEX_EXEC_TIMEOUT_SECONDS} 秒，重试 {attempts} 次仍失败），请检查当前模型配置或登录态。"
                )
        except asyncio.CancelledError:
            if process is not None:
                logger.warning(
                    "codex_exec_cancelled mode=structured attempt=%s/%s pid=%s",
                    attempt,
                    attempts,
                    getattr(process, "pid", 0),
                )
                await _terminate_process(process)
            raise

        logger.info(
            "codex_exec_end mode=structured attempt=%s/%s pid=%s returncode=%s elapsed_ms=%s stdout_chars=%s stderr_chars=%s",
            attempt,
            attempts,
            getattr(process, "pid", 0),
            process.returncode,
            int((time.monotonic() - started_at) * 1000),
            len(stdout or b""),
            len(stderr or b""),
        )
        if process.returncode != 0:
            message = _format_codex_error(
                stdout.decode("utf-8", errors="ignore"),
                stderr.decode("utf-8", errors="ignore"),
            )
            if attempt < attempts and _is_retryable_codex_error(message):
                continue
            raise ValueError(message)

        if not output_path.exists():
            if attempt < attempts:
                continue
            raise ValueError("Codex CLI 未生成最终输出")

        raw = output_path.read_text(encoding="utf-8").strip()
        if not raw:
            if attempt < attempts:
                continue
            raise ValueError("Codex CLI 返回了空结果")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            if attempt < attempts:
                continue
            raise ValueError(f"Codex CLI 返回了不可解析结果: {raw}")

    raise ValueError("Codex CLI 执行失败")


def _is_retryable_codex_error(message: str) -> bool:
    lowered = (message or "").lower()
    return "timeout" in lowered or "temporarily unavailable" in lowered


async def _run_codex_simple_with_retry(args: list[str], prompt: str, work_dir: str) -> str:
    attempts = max(1, _CODEX_EXEC_MAX_ATTEMPTS)
    for attempt in range(1, attempts + 1):
        process = None
        started_at = time.monotonic()
        try:
            logger.info(
                "codex_exec_start mode=simple attempt=%s/%s timeout=%ss work_dir=%s arg_count=%s prompt_chars=%s",
                attempt,
                attempts,
                _CODEX_EXEC_TIMEOUT_SECONDS,
                work_dir,
                len(args),
                len(prompt),
            )
            process = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir or None,
                env=_build_codex_env(),
                start_new_session=True,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=prompt.encode("utf-8")),
                    timeout=_CODEX_EXEC_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "codex_exec_timeout mode=simple attempt=%s/%s pid=%s elapsed_ms=%s",
                    attempt,
                    attempts,
                    getattr(process, "pid", 0),
                    int((time.monotonic() - started_at) * 1000),
                )
                await _terminate_process(process)
                if attempt < attempts:
                    continue
                raise ValueError(
                    f"Codex CLI 执行超时（>{_CODEX_EXEC_TIMEOUT_SECONDS} 秒，重试 {attempts} 次仍失败），请检查当前模型配置或登录态。"
                )
        except asyncio.CancelledError:
            if process is not None:
                logger.warning(
                    "codex_exec_cancelled mode=simple attempt=%s/%s pid=%s",
                    attempt,
                    attempts,
                    getattr(process, "pid", 0),
                )
                await _terminate_process(process)
            raise

        logger.info(
            "codex_exec_end mode=simple attempt=%s/%s pid=%s returncode=%s elapsed_ms=%s stdout_chars=%s stderr_chars=%s",
            attempt,
            attempts,
            getattr(process, "pid", 0),
            process.returncode,
            int((time.monotonic() - started_at) * 1000),
            len(stdout or b""),
            len(stderr or b""),
        )
        stdout_text = stdout.decode("utf-8", errors="ignore")
        stderr_text = stderr.decode("utf-8", errors="ignore")
        if process.returncode != 0:
            message = _format_codex_error(stdout_text, stderr_text)
            if attempt < attempts and _is_retryable_codex_error(message):
                continue
            raise ValueError(message)

        content = _extract_simple_content(stdout_text)
        if content:
            return content
        if attempt < attempts:
            continue
        raise ValueError("Codex CLI 返回了空结果")

    raise ValueError("Codex CLI 执行失败")


def _extract_simple_content(stdout_text: str) -> str:
    text = stdout_text.replace("\r\n", "\n").strip()
    if not text:
        return ""
    marker = "\ncodex\n"
    index = text.rfind(marker)
    if index != -1:
        payload = text[index + len(marker):]
    elif text.startswith("codex\n"):
        payload = text[len("codex\n"):]
    else:
        payload = text

    token_marker = "\ntokens used"
    if token_marker in payload:
        payload = payload.split(token_marker, 1)[0]
    return payload.strip()
