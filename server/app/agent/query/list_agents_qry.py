"""
app/agent/query/list_agents_qry.py

查询 Agent 图列表/详情的响应数据结构。
"""

from dataclasses import dataclass, field
from typing import Optional

from server.domain.agent.entity.agent_entity import EdgeCondition, LLMProvider


@dataclass
class AgentNodeVO:
    id: str
    name: str
    provider: LLMProvider
    model: str
    system_prompt: str
    temperature: float
    max_tokens: int
    tools: list[str]


@dataclass
class GraphEdgeVO:
    from_node: str
    to_node: str
    condition: EdgeCondition
    condition_expr: Optional[str]


@dataclass
class GraphVO:
    id: str
    name: str
    entry_node: str
    agents: list[AgentNodeVO] = field(default_factory=list)
    edges: list[GraphEdgeVO] = field(default_factory=list)
