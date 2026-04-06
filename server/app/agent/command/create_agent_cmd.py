"""
app/agent/command/create_agent_cmd.py

创建/更新 Agent 图配置的命令对象（数据载体，无业务逻辑）。
"""

from dataclasses import dataclass, field
from typing import Optional

from server.domain.agent.entity.agent_entity import EdgeCondition, LLMProvider


@dataclass
class AgentNodeCmd:
    id: str
    name: str
    provider: LLMProvider
    model: str
    system_prompt: str
    temperature: float = 0.7
    max_tokens: int = 4096
    tools: list[str] = field(default_factory=list)


@dataclass
class GraphEdgeCmd:
    from_node: str
    to_node: str
    condition: EdgeCondition = EdgeCondition.ALWAYS
    condition_expr: Optional[str] = None


@dataclass
class CreateGraphCmd:
    """创建新图配置的命令"""
    name: str
    entry_node: str
    agents: list[AgentNodeCmd] = field(default_factory=list)
    edges: list[GraphEdgeCmd] = field(default_factory=list)


@dataclass
class UpdateGraphCmd:
    """更新已有图配置的命令（全量替换）"""
    graph_id: str
    name: str
    entry_node: str
    agents: list[AgentNodeCmd] = field(default_factory=list)
    edges: list[GraphEdgeCmd] = field(default_factory=list)
