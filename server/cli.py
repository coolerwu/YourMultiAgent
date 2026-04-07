"""
server/cli.py

yourmultiagent CLI 入口（Typer）：

  yourmultiagent start   [--port 8080] [--dev] [--data-dir PATH]
  yourmultiagent worker  --server ws://HOST:PORT [--name NAME]
  yourmultiagent init

安装方式：pip install -e .（项目根目录）
"""

import asyncio
import os
import socket
from pathlib import Path

import typer

app = typer.Typer(name="yourmultiagent", help="个人多 Agent 平台 CLI")


def _resolve_data_dir(dev: bool, data_dir: str | None) -> Path:
    if data_dir:
        return Path(data_dir).expanduser().resolve()
    if dev:
        return Path("./data").resolve()
    return Path.home() / ".yourmultiagent"


@app.command()
def start(
    port: int = typer.Option(8080, "--port", help="服务端口"),
    dev: bool = typer.Option(False, "--dev", help="开发模式：数据存储在 ./data/"),
    data_dir: str = typer.Option(None, "--data-dir", help="数据目录（覆盖默认路径）"),
    reload: bool = typer.Option(False, "--reload", help="热重载（仅开发时使用）"),
) -> None:
    """启动 Central Server（生产模式默认读取 ~/.yourmultiagent/）"""
    import uvicorn

    dir_path = _resolve_data_dir(dev, data_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    os.environ["DATA_DIR"] = str(dir_path)

    mode = "开发" if dev else "生产"
    typer.echo(f"▶  启动 YourMultiAgent Server（{mode}模式）")
    typer.echo(f"   数据目录：{dir_path}")
    typer.echo(f"   地址：http://0.0.0.0:{port}")

    uvicorn.run("server.main:app", host="0.0.0.0", port=port, reload=reload)


@app.command()
def worker(
    server: str = typer.Option("ws://localhost:8080", "--server", help="Central Server WebSocket 地址"),
    name: str = typer.Option(None, "--name", help="Worker 名称（默认：主机名）"),
) -> None:
    """启动 Remote Worker，连接到 Central Server 并注册本机 capabilities"""
    from server.infra.worker.ws_worker_client import WsWorkerClient

    worker_name = name or socket.gethostname()
    typer.echo(f"▶  启动 Worker '{worker_name}'")
    typer.echo(f"   连接到：{server}")

    client = WsWorkerClient(server, worker_name)
    asyncio.run(client.start())


@app.command()
def init() -> None:
    """初始化 ~/.yourmultiagent/ 目录和默认配置"""
    import json

    data_dir = Path.home() / ".yourmultiagent"
    data_dir.mkdir(parents=True, exist_ok=True)

    config_path = data_dir / "config.json"
    if not config_path.exists():
        config_path.write_text(
            json.dumps({"version": "0.1.0"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    typer.echo(f"✓ 已初始化：{data_dir}")
    typer.echo(f"  启动命令：yourmultiagent start")
