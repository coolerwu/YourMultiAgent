"""
infra/llm/codex_cli_adapter.py

将本机 Codex CLI 包装为可被当前 Agent 链路消费的聊天模型适配器。
"""

from __future__ import annotations

import asyncio
import json
import os
import pty
import select
import shutil
import signal
import time
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk

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


_CODEX_EXEC_TIMEOUT_SECONDS = _int_env("YOURMULTIAGENT_CODEX_EXEC_TIMEOUT_SECONDS", 120)
_CODEX_EXEC_MAX_ATTEMPTS = _int_env("YOURMULTIAGENT_CODEX_EXEC_MAX_ATTEMPTS", 2)
_CODEX_SANDBOX_MODE = (os.environ.get("YOURMULTIAGENT_CODEX_SANDBOX_MODE", "read-only") or "").strip() or "read-only"
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
        structured_output = not self._simple_output_mode or bool(self._tools)
        if structured_output:
            result = await self._run(messages)
            yield AIMessageChunk(
                content=result.content,
                additional_kwargs=dict(getattr(result, "additional_kwargs", {}) or {}),
                response_metadata=dict(getattr(result, "response_metadata", {}) or {}),
                name=getattr(result, "name", None),
                id=getattr(result, "id", None),
                tool_calls=list(getattr(result, "tool_calls", None) or []),
                invalid_tool_calls=list(getattr(result, "invalid_tool_calls", None) or []),
                usage_metadata=getattr(result, "usage_metadata", None),
                chunk_position="last",
            )
            return

        if not self._codex_path:
            raise ValueError("未检测到本机 codex CLI")

        prompt = _build_exec_prompt(messages, self._tools, structured_output=False)
        pending_delta = ""
        async for delta in _stream_codex_text_with_retry(self._build_exec_args(prompt), self._work_dir or ""):
            if not delta:
                continue
            if pending_delta:
                yield AIMessageChunk(content=pending_delta)
            pending_delta = delta

        if not pending_delta:
            raise ValueError("Codex CLI 返回了空结果")

        yield AIMessageChunk(content=pending_delta, chunk_position="last")

    async def _run(self, messages: list[Any]) -> AIMessage:
        if not self._codex_path:
            raise ValueError("未检测到本机 codex CLI")

        structured_output = not self._simple_output_mode or bool(self._tools)
        prompt = _build_exec_prompt(messages, self._tools, structured_output=structured_output)
        stdout_text = await _run_codex_with_retry(self._build_exec_args(prompt), self._work_dir or "")
        assistant_text = _extract_assistant_text(stdout_text)
        if not assistant_text:
            raise ValueError("Codex CLI 返回了空结果")

        if not structured_output:
            return AIMessage(content=assistant_text, tool_calls=[])

        data = _extract_structured_result(assistant_text)
        return AIMessage(
            content=str(data.get("content", "")).strip(),
            tool_calls=_normalize_tool_calls(data.get("tool_calls", [])),
        )

    def _build_exec_args(self, prompt: str) -> list[str]:
        args = [
            self._codex_path,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            _CODEX_SANDBOX_MODE,
            "--color",
            "never",
            "--json",
        ]
        if self._model:
            args.extend(["--model", self._model])
        if self._work_dir:
            args.extend(["-C", self._work_dir])
        args.append(prompt)
        return args


def _build_exec_prompt(messages: list[Any], tools: list[dict], *, structured_output: bool) -> str:
    lines = [
        "你是多 Agent 平台中的底层推理模型适配器。",
        "禁止调用 Codex 内置工具、exec_command、shell、文件系统、网络请求或任何外部执行能力。",
        "你只能基于提供的消息内容推理，然后直接给出最终结果。",
    ]
    if structured_output:
        lines.extend(
            [
                "你必须只输出一个 JSON 对象，不要输出解释、不要输出 Markdown、不要输出代码块。",
                "允许的顶层字段只有 content 和 tool_calls。",
                "content 必须是字符串。",
            ]
        )
    else:
        lines.append("请直接输出最终回答正文，不要添加额外 JSON 包装。")

    if tools and structured_output:
        lines.extend(
            [
                "当且仅当确实需要平台工具时，才在 tool_calls 中返回待调用工具。",
                "tool_calls 必须是数组，每个元素都必须包含 id、name、args。",
                "如果不需要工具，tool_calls 必须返回空数组。",
                "只能从以下工具中选择：",
            ]
        )
        for tool in tools:
            lines.append(f"- {tool.get('name')}: {tool.get('description', '')}")
    elif structured_output:
        lines.append("tool_calls 必须返回空数组。")

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
        normalized.append(
            {
                "id": str(item.get("id") or f"tool_call_{index}"),
                "name": name,
                "args": args,
            }
        )
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
    if "failed rtm_newaddr" in lowered and "operation not permitted" in lowered:
        return (
            "Codex CLI 执行失败：当前宿主机不允许 Codex 的 read-only sandbox 创建隔离网络/loopback。"
            "这不是 prompt 或参数格式问题，而是运行环境对 bubblewrap/net namespace 的权限限制。"
        )
    if (
        "responses_websocket" in lowered
        and "operation not permitted" in lowered
    ) or (
        "chatgpt.com/backend-api/codex/responses" in lowered
        and ("operation not permitted" in lowered or "error sending request for url" in lowered)
    ):
        return (
            "Codex CLI 执行失败：当前运行环境禁止 Codex 访问 ChatGPT Codex 实时响应通道。"
            "日志里已经出现 `responses_websocket` / `Operation not permitted`，这通常意味着宿主机、沙箱或企业网络策略拦截了"
            " `wss://chatgpt.com/backend-api/codex/responses`。"
        )
    if "could not create otel exporter" in lowered:
        return (
            "Codex CLI 执行失败：Codex 进程启动时初始化 OTEL 导出器失败。"
            "当前版本会尽量清理 OTEL 相关环境变量；如果仍复现，通常说明宿主环境里还有额外的观测配置注入。"
        )
    return ""


def _build_codex_env() -> dict[str, str]:
    return build_codex_subprocess_env(os.environ)


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


async def _run_codex_with_retry(args: list[str], work_dir: str) -> str:
    attempts = max(1, _CODEX_EXEC_MAX_ATTEMPTS)
    for attempt in range(1, attempts + 1):
        process = None
        started_at = time.monotonic()
        try:
            logger.info(
                "codex_exec_start attempt=%s/%s timeout=%ss work_dir=%s arg_count=%s",
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
                stderr=asyncio.subprocess.DEVNULL,
                cwd=work_dir or None,
                env=_build_codex_env(),
                start_new_session=True,
            )
            try:
                stdout, _ = await _read_process_output(process)
            except asyncio.TimeoutError:
                logger.warning(
                    "codex_exec_timeout attempt=%s/%s pid=%s elapsed_ms=%s",
                    attempt,
                    attempts,
                    getattr(process, "pid", 0),
                    int((time.monotonic() - started_at) * 1000),
                )
                await _terminate_process(process)
                if attempt < attempts:
                    continue
                raise ValueError(
                    f"Codex CLI 执行超时（>{_CODEX_EXEC_TIMEOUT_SECONDS} 秒，重试 {attempts} 次仍失败）。\n"
                    "这通常意味着 codex exec 进程卡住（例如 CLI 版本缺陷或本机环境兼容性问题），建议先升级 Codex CLI 后重试。"
                )
        except BaseException:
            if process is not None:
                logger.warning(
                    "codex_exec_cancelled attempt=%s/%s pid=%s",
                    attempt,
                    attempts,
                    getattr(process, "pid", 0),
                )
                await _terminate_process(process)
            raise

        logger.info(
            "codex_exec_end attempt=%s/%s pid=%s returncode=%s elapsed_ms=%s stdout_chars=%s",
            attempt,
            attempts,
            getattr(process, "pid", 0),
            process.returncode,
            int((time.monotonic() - started_at) * 1000),
            len(stdout or b""),
        )
        stdout_text = stdout.decode("utf-8", errors="ignore")
        # stderr 被重定向到 DEVNULL，错误信息通过 stdout 获取
        if process.returncode != 0:
            message = _format_codex_error(stdout_text, "")
            if attempt < attempts and _is_retryable_codex_error(message):
                continue
            raise ValueError(message)

        if stdout_text.strip():
            return stdout_text
        if attempt < attempts:
            continue
        raise ValueError("Codex CLI 返回了空结果")

    raise ValueError("Codex CLI 执行失败")


async def _stream_codex_text_with_retry(args: list[str], work_dir: str):
    """
    使用 PTY 强制行缓冲，解决 Codex 在非 TTY 环境下全缓冲导致 readline 阻塞的问题。
    """
    attempts = max(1, _CODEX_EXEC_MAX_ATTEMPTS)
    for attempt in range(1, attempts + 1):
        process = None
        started_at = time.monotonic()
        emitted_any = False
        stdout_chunks: list[bytes] = []
        stderr_chunks: list[bytes] = []
        master_fd = None
        slave_fd = None

        try:
            logger.info(
                "codex_exec_stream_start attempt=%s/%s timeout=%ss work_dir=%s arg_count=%s",
                attempt,
                attempts,
                _CODEX_EXEC_TIMEOUT_SECONDS,
                work_dir,
                len(args),
            )

            # 使用 PTY 让 Codex 认为自己在终端中运行（强制行缓冲）
            master_fd, slave_fd = pty.openpty()

            process = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=work_dir or None,
                env=_build_codex_env(),
                start_new_session=True,
            )

            os.close(slave_fd)
            slave_fd = None

            # 将 PTY master 转为非阻塞模式
            os.set_blocking(master_fd, False)

            loop = asyncio.get_event_loop()
            buffer = b""

            while True:
                try:
                    # 使用 select 等待数据可读
                    readable, _, _ = await loop.run_in_executor(
                        None,
                        lambda: select.select([master_fd], [], [], 0.1)
                    )

                    if readable:
                        chunk = os.read(master_fd, 4096)
                        if not chunk:
                            break
                        buffer += chunk

                        # 处理缓冲区中的完整行
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            line += b"\n"
                            stdout_chunks.append(line)
                            event = _parse_json_event_line(line.decode("utf-8", errors="ignore"))
                            if event:
                                delta = _extract_stream_text_delta(event)
                                if delta:
                                    emitted_any = True
                                    yield delta

                    # 检查进程是否结束
                    if process.returncode is not None:
                        break

                except OSError:
                    break

            # 读取剩余数据
            if buffer:
                stdout_chunks.append(buffer)

            await asyncio.wait_for(process.wait(), timeout=5)

        except asyncio.TimeoutError:
            logger.warning(
                "codex_exec_stream_timeout attempt=%s/%s pid=%s elapsed_ms=%s",
                attempt,
                attempts,
                getattr(process, "pid", 0),
                int((time.monotonic() - started_at) * 1000),
            )
            if master_fd is not None:
                try:
                    os.close(master_fd)
                except OSError:
                    pass
            if slave_fd is not None:
                try:
                    os.close(slave_fd)
                except OSError:
                    pass
            if process is not None:
                await _terminate_process(process)
            if attempt < attempts and not emitted_any:
                continue
            raise ValueError(
                f"Codex CLI 执行超时（>{_CODEX_EXEC_TIMEOUT_SECONDS} 秒，重试 {attempts} 次仍失败）。\n"
                "这通常意味着 codex exec 进程卡住（例如 CLI 版本缺陷或本机环境兼容性问题），建议先升级 Codex CLI 后重试。"
            )
        except BaseException:
            if master_fd is not None:
                try:
                    os.close(master_fd)
                except OSError:
                    pass
            if slave_fd is not None:
                try:
                    os.close(slave_fd)
                except OSError:
                    pass
            if process is not None:
                logger.warning(
                    "codex_exec_stream_cancelled attempt=%s/%s pid=%s",
                    attempt,
                    attempts,
                    getattr(process, "pid", 0),
                )
                await _terminate_process(process)
            raise
        finally:
            if master_fd is not None:
                try:
                    os.close(master_fd)
                except OSError:
                    pass

        stdout = b"".join(stdout_chunks)
        stderr = b"".join(stderr_chunks)
        logger.info(
            "codex_exec_stream_end attempt=%s/%s pid=%s returncode=%s elapsed_ms=%s stdout_chars=%s",
            attempt,
            attempts,
            getattr(process, "pid", 0),
            getattr(process, "returncode", None),
            int((time.monotonic() - started_at) * 1000),
            len(stdout or b""),
        )
        stdout_text = stdout.decode("utf-8", errors="ignore")
        if process is None:
            raise ValueError("Codex CLI 执行失败")
        if process.returncode != 0:
            message = _format_codex_error(stdout_text, "")
            if attempt < attempts and not emitted_any and _is_retryable_codex_error(message):
                continue
            raise ValueError(message)

        # 如果没有产出任何 delta，但 stdout 有内容，尝试解析为最终输出
        if not emitted_any and stdout_text.strip():
            assistant_text = _extract_assistant_text(stdout_text)
            if assistant_text:
                yield assistant_text

        if emitted_any:
            return

        assistant_text = _extract_assistant_text(stdout_text)
        if assistant_text:
            yield assistant_text
            return
        if attempt < attempts:
            continue
        raise ValueError("Codex CLI 返回了空结果")

    raise ValueError("Codex CLI 执行失败")


async def _read_process_output(process: asyncio.subprocess.Process) -> tuple[bytes, bytes]:
    stdout_stream = getattr(process, "stdout", None)
    if stdout_stream is None or not hasattr(stdout_stream, "readline"):
        return await asyncio.wait_for(
            process.communicate(),
            timeout=_CODEX_EXEC_TIMEOUT_SECONDS,
        )

    chunks: list[bytes] = []
    while True:
        line = await asyncio.wait_for(stdout_stream.readline(), timeout=_CODEX_EXEC_TIMEOUT_SECONDS)
        if not line:
            break
        chunks.append(line)

    await asyncio.wait_for(process.wait(), timeout=5)
    return b"".join(chunks), b""


def _is_retryable_codex_error(message: str) -> bool:
    lowered = (message or "").lower()
    return "timeout" in lowered or "temporarily unavailable" in lowered


def _extract_assistant_text(stdout_text: str) -> str:
    events = _parse_jsonl_events(stdout_text)
    if not events:
        return _strip_plaintext_noise(stdout_text)

    messages: list[str] = []
    for event in events:
        content = _extract_event_text(event)
        if content:
            messages.append(content)
    return messages[-1].strip() if messages else ""


def _parse_jsonl_events(stdout_text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_line in stdout_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _parse_json_event_line(raw_line: str) -> dict[str, Any] | None:
    line = (raw_line or "").strip()
    if not line:
        return None
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _extract_event_text(event: dict[str, Any]) -> str:
    event_type = str(event.get("type", "")).strip()
    if event_type == "message" and str(event.get("role", "")).strip() == "assistant":
        return _coerce_text(event.get("content"))
    if event_type == "item.completed":
        item = event.get("item")
        if isinstance(item, dict) and str(item.get("type", "")).strip() == "agent_message":
            return _coerce_text(item.get("text") or item.get("content"))
    if event_type in {"agent_message", "assistant_message"}:
        return _coerce_text(event.get("text") or event.get("content"))
    return ""


def _extract_stream_text_delta(event: dict[str, Any]) -> str:
    event_type = str(event.get("type", "")).strip()
    if event_type in {"agent_message_delta", "assistant_message_delta"}:
        return _coerce_text(event.get("delta") or event.get("text") or event.get("content"))
    if event_type in {"agent_message_content_delta", "assistant_message_content_delta"}:
        return _coerce_text(event.get("delta"))
    if event_type == "item.updated":
        item = event.get("item")
        if isinstance(item, dict) and str(item.get("type", "")).strip() == "agent_message":
            return _coerce_text(item.get("delta"))
    return ""


def _coerce_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [str(item.get("text", "")).strip() for item in value if isinstance(item, dict)]
        return "\n".join(part for part in parts if part).strip()
    return str(value or "").strip()


def _strip_plaintext_noise(stdout_text: str) -> str:
    lines = []
    for raw_line in stdout_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("Reading additional input from stdin"):
            continue
        lines.append(raw_line)
    return "\n".join(lines).strip()


def _extract_structured_result(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = _strip_code_fences(raw)
    decoder = json.JSONDecoder()
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError(f"Codex CLI 返回了不可解析结果: {text}")


def _strip_code_fences(text: str) -> str:
    lines = text.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text
