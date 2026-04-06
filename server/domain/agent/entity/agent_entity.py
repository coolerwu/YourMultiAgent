"""
domain/agent/entity/agent_entity.py

Agent 配置实体与 Graph 结构值对象。
AgentEntity  — 单个 Agent 的配置（角色、模型、系统提示）
GraphEntity  — 由多个 Agent 节点 + 有向边组成的执行图配置
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LLMProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class EdgeCondition(str, Enum):
    """边的触发条件"""
    ALWAYS = "always"       # 无条件流转
    ON_SUCCESS = "on_success"
    ON_FAILURE = "on_failure"
    CONDITIONAL = "conditional"  # 由 LLM 输出决定


@dataclass
class AgentEntity:
    """单个 Agent 节点配置"""
    id: str                          # 节点唯一 ID，页面生成
    name: str                        # 展示名
    provider: LLMProvider
    model: str                       # 模型名，如 claude-sonnet-4-6
    system_prompt: str
    temperature: float = 0.7
    max_tokens: int = 4096
    tools: list[str] = field(default_factory=list)  # 白名单 capability 名称列表


@dataclass
class GraphEdge:
    """有向边：from_node → to_node"""
    from_node: str
    to_node: str
    condition: EdgeCondition = EdgeCondition.ALWAYS
    condition_expr: Optional[str] = None  # CONDITIONAL 时的判断表达式


@dataclass
class GraphEntity:
    """Agent 执行图配置（值对象）"""
    id: str
    name: str
    entry_node: str                          # 图的起始节点 ID
    agents: list[AgentEntity] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    def get_agent(self, agent_id: str) -> Optional[AgentEntity]:
        return next((a for a in self.agents if a.id == agent_id), None)

    def get_outgoing_edges(self, agent_id: str) -> list[GraphEdge]:
        return [e for e in self.edges if e.from_node == agent_id]
