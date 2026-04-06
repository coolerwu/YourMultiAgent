"""
app/agent/command/run_agent_cmd.py

触发 Agent 图执行的命令。
"""

from dataclasses import dataclass


@dataclass
class RunGraphCmd:
    graph_id: str
    user_message: str
    session_id: str = ""   # 预留：多轮对话会话 ID
