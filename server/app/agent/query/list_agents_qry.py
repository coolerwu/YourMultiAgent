"""
app/agent/query/list_agents_qry.py

查询 Agent 图列表/详情的响应数据结构。
新增字段：AgentNodeVO.base_url/api_key/work_subdir，GraphVO.workspace_id
"""

from dataclasses import dataclass, field
from typing import Optional

from server.domain.agent.agent_entity import EdgeCondition, LLMProvider


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
    llm_profile_id: str = ""
    codex_connection_id: str = ""
    base_url: str = ""
    api_key: str = ""
    work_subdir: str = ""


@dataclass
class GraphEdgeVO:
    from_node: str
    to_node: str
    condition: EdgeCondition
    condition_expr: Optional[str]
    artifact: str = ""
    prompt: str = ""


@dataclass
class GraphVO:
    id: str
    name: str
    entry_node: str
    agents: list[AgentNodeVO] = field(default_factory=list)
    edges: list[GraphEdgeVO] = field(default_factory=list)
    workspace_id: str = ""
