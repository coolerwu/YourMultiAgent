"""
app/agent/command/create_agent_cmd.py

创建/更新 Agent 图配置的命令对象（数据载体，无业务逻辑）。
新增字段：AgentNodeCmd.base_url/api_key/work_subdir，CreateGraphCmd/UpdateGraphCmd.workspace_id
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
    llm_profile_id: str = ""
    codex_connection_id: str = ""
    base_url: str = ""       # openai_compat 时必填，其余可留空
    api_key: str = ""        # 节点级覆盖；留空则用环境变量
    work_subdir: str = ""    # 相对于 workspace.work_dir 的子目录名，默认 = agent.name
    order: int = 0           # Worker 执行顺序；数字越小越先执行


@dataclass
class GraphEdgeCmd:
    from_node: str
    to_node: str
    condition: EdgeCondition = EdgeCondition.ALWAYS
    condition_expr: Optional[str] = None
    artifact: str = ""      # 触发条件文件名
    prompt: str = ""        # 传递给下一个 Agent 的指令


@dataclass
class CreateGraphCmd:
    """创建新图配置的命令"""
    name: str
    entry_node: str
    agents: list[AgentNodeCmd] = field(default_factory=list)
    edges: list[GraphEdgeCmd] = field(default_factory=list)
    workspace_id: str = ""   # 关联的 Workspace ID


@dataclass
class UpdateGraphCmd:
    """更新已有图配置的命令（全量替换）"""
    graph_id: str
    name: str
    entry_node: str
    agents: list[AgentNodeCmd] = field(default_factory=list)
    edges: list[GraphEdgeCmd] = field(default_factory=list)
    workspace_id: str = ""   # 关联的 Workspace ID
