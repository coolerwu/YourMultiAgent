"""
server/config.py

DATA_DIR 解析逻辑：
  - 优先读取环境变量 DATA_DIR
  - 未设置时 fallback 到 ./data（本地 python server/main.py 开发模式）
  - CLI 命令 `yourmultiagent start` 启动前会设置 DATA_DIR=~/.yourmultiagent
"""

import os
from pathlib import Path


def get_data_dir() -> Path:
    """返回数据目录的绝对路径，不存在时自动创建。"""
    env = os.environ.get("DATA_DIR")
    if env:
        p = Path(env).expanduser().resolve()
    else:
        p = Path("./data").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p
