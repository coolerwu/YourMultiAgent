"""
app/agent/command/optimize_prompt_cmd.py

优化 Agent System Prompt 的命令对象。
"""

from dataclasses import dataclass, field

from server.domain.agent.entity.agent_entity import LLMProvider


@dataclass
class OptimizePromptCmd:
    name: str
    system_prompt: str
    prompt_kind: str = "system_prompt"
    goal: str = ""
    workspace_id: str = ""
    source_name: str = ""
    target_name: str = ""
    artifact: str = ""
    provider: LLMProvider = LLMProvider.ANTHROPIC
    model: str = "claude-sonnet-4-6"
    temperature: float = 0.2
    max_tokens: int = 4096
    tools: list[str] = field(default_factory=list)
    llm_profile_id: str = ""
    codex_connection_id: str = ""
    base_url: str = ""
    api_key: str = ""
