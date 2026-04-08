"""
app/agent/command/generate_worker_cmd.py

AI 生成 Worker 草稿的命令对象。
"""

from dataclasses import dataclass, field

from server.domain.agent.entity.agent_entity import LLMProvider


@dataclass
class GenerateWorkerCmd:
    workspace_id: str = ""
    user_goal: str = ""
    coordinator_name: str = ""
    coordinator_prompt: str = ""
    existing_worker_names: list[str] = field(default_factory=list)
    available_tools: list[str] = field(default_factory=list)
    provider: LLMProvider = LLMProvider.ANTHROPIC
    model: str = "claude-sonnet-4-6"
    llm_profile_id: str = ""
    codex_connection_id: str = ""
    base_url: str = ""
    api_key: str = ""
