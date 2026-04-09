import os
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage

from server.infra.codex import codex_cli
import server.infra.llm.codex_cli_adapter as codex_cli_adapter
from server.infra.llm.codex_cli_adapter import CodexCLIAdapter


def test_build_install_command_uses_user_prefix(monkeypatch):
    monkeypatch.setattr(codex_cli, "os_family", lambda: "linux")
    monkeypatch.setattr(Path, "home", lambda: Path("/home/qiuqiu"))

    assert codex_cli.build_install_command() == [
        "npm",
        "install",
        "-g",
        "@openai/codex",
        "--prefix",
        "/home/qiuqiu/.local",
    ]

    assert codex_cli.build_install_manual_command() == "npm install -g @openai/codex --prefix /home/qiuqiu/.local"


def test_detect_codex_path_falls_back_to_user_bin(monkeypatch):
    monkeypatch.setattr(codex_cli, "os_family", lambda: "linux")
    monkeypatch.setattr(Path, "home", lambda: Path("/home/qiuqiu"))
    monkeypatch.setattr(codex_cli.shutil, "which", lambda _name: "")
    monkeypatch.setattr(codex_cli.os.path, "exists", lambda path: path == "/home/qiuqiu/.local/bin/codex")
    monkeypatch.setattr(codex_cli.os, "access", lambda path, _mode: path == "/home/qiuqiu/.local/bin/codex")

    assert codex_cli.detect_codex_path() == "/home/qiuqiu/.local/bin/codex"


def _require_manual_smoke(flag_name: str) -> None:
    if os.environ.get(flag_name, "").strip() == "1":
        return
    pytest.skip(
        f"手动 smoke 测试默认跳过；如需执行，请先设置 {flag_name}=1",
    )


def test_real_codex_cli_runtime_smoke():
    _require_manual_smoke("YOURMULTIAGENT_RUN_REAL_CODEX_SMOKE")

    node_path = codex_cli.detect_node_path()
    npm_path = codex_cli.detect_npm_path()
    codex_path = codex_cli.detect_codex_path()
    cli_version = codex_cli.detect_cli_version(codex_path)
    login_status, login_details = codex_cli.detect_login_status(codex_path)

    print(f"node_path={node_path}")
    print(f"npm_path={npm_path}")
    print(f"codex_path={codex_path}")
    print(f"cli_version={cli_version}")
    print(f"login_status={login_status}")
    print(f"login_details={login_details}")

    assert node_path, "未检测到 node，可先排查 Node.js 安装"
    assert npm_path, "未检测到 npm，可先排查 Node.js/npm 安装"
    assert codex_path, "未检测到 codex CLI，可先排查安装路径/PATH"
    assert cli_version, "已找到 codex CLI，但 --version 未返回有效版本"
    assert login_status == "connected", f"codex login status={login_status}\n{login_details}"


@pytest.mark.asyncio
async def test_real_codex_cli_exec_smoke(monkeypatch):
    _require_manual_smoke("YOURMULTIAGENT_RUN_REAL_CODEX_EXEC")

    codex_path = codex_cli.detect_codex_path()
    assert codex_path, "未检测到 codex CLI，可先运行 runtime smoke 定位安装问题"

    monkeypatch.setattr(codex_cli_adapter, "_CODEX_EXEC_TIMEOUT_SECONDS", 30)
    monkeypatch.setattr(codex_cli_adapter, "_CODEX_EXEC_MAX_ATTEMPTS", 1)
    adapter = CodexCLIAdapter(model="", codex_path=codex_path, simple_output_mode=True)

    result = await adapter.ainvoke([HumanMessage(content="请只输出 OK，不要输出别的内容。")])

    print(f"assistant_content={result.content}")
    assert result.content.strip(), "codex exec 成功返回，但内容为空"


@pytest.mark.asyncio
async def test_real_codex_cli_astream_smoke(monkeypatch):
    _require_manual_smoke("YOURMULTIAGENT_RUN_REAL_CODEX_ASTREAM")

    codex_path = codex_cli.detect_codex_path()
    assert codex_path, "未检测到 codex CLI，可先运行 runtime smoke 定位安装问题"

    monkeypatch.setattr(codex_cli_adapter, "_CODEX_EXEC_TIMEOUT_SECONDS", 30)
    monkeypatch.setattr(codex_cli_adapter, "_CODEX_EXEC_MAX_ATTEMPTS", 1)
    adapter = CodexCLIAdapter(model="", codex_path=codex_path, simple_output_mode=True)

    chunks = [chunk async for chunk in adapter.astream([HumanMessage(content="请只输出 OK，不要输出别的内容。")])]

    print(f"chunk_count={len(chunks)}")
    for index, chunk in enumerate(chunks, start=1):
        print(f"chunk_{index}_content={chunk.content}")

    assert chunks, "astream 没有产出任何 chunk"
    assert chunks[-1].content.strip(), "astream 最终 chunk 为空"
