"""
domain/agent/agent_entity.py

Agent 配置实体、Graph 结构值对象、Workspace 实体。
AgentEntity     — 单个 Agent / Worker 配置（含 api_key 覆盖）
GraphEdge       — 遗留有向边：from_node → to_node，支持 artifact 文件触发
GraphEntity     — 遗留图模型
WorkspaceEntity — 运行时环境：共享根目录 + 单编排配置

协作模型：
  所有 Worker 共享 WorkspaceEntity.work_dir 作为根目录。
  边的 artifact 字段指定一个文件名（相对于根目录）：
    - artifact 非空 → 文件存在时才触发该边（文件驱动路由）
    - artifact 为空 → 作为默认 fallback
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LLMProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENAI_COMPAT = "openai_compat"   # 任意 OpenAI 兼容 API（DeepSeek/Moonshot 等）
    OPENAI_CODEX = "openai_codex"


class WorkspaceKind(str, Enum):
    WORKSPACE = "workspace"
    CHAT = "chat"


class EdgeCondition(str, Enum):
    """遗留字段：旧条件边类型，运行时已不再使用。"""
    ALWAYS = "always"
    ON_SUCCESS = "on_success"
    ON_FAILURE = "on_failure"
    CONDITIONAL = "conditional"


@dataclass
class GitWorkflowConfig:
    """Git 工作流配置"""
    enabled: bool = False
    repoUrl: str = ""
    baseBranch: str = "main"
    featureBranchPrefix: str = "feature/"
    autoCreateBranch: bool = True
    autoCommit: bool = True
    commitMessageTemplate: str = "[Agent] {{task_name}}"
    prTitleTemplate: str = "[Agent] {{task_name}}"
    prBodyTemplate: str = "## 任务描述\n{{task_description}}\n\n## 变更内容\n- 由 Agent 自动生成\n"
    autoCreatePR: bool = False
    requireReview: bool = True


@dataclass
class AgentEntity:
    """单个 Agent 节点配置"""
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
    # OpenAI-compat 节点级覆盖（留空则用 workspace 默认或环境变量）
    base_url: str = ""
    api_key: str = ""
    # 运行时工作子目录（相对于 workspace.work_dir，默认 = agent.name）
    work_subdir: str = ""
    # Worker 执行顺序；coordinator 固定为 0
    order: int = 0
    # Git 工作流配置（仅 Coordinator 有效）
    git_workflow: GitWorkflowConfig | None = None

    def resolved_work_subdir(self) -> str:
        """返回实际子目录名，未配置时退化为 agent name"""
        return self.work_subdir or self.name


@dataclass
class GraphEdge:
    """
    有向边：from_node → to_node

    artifact 非空时：检查 workspace 根目录下该文件是否存在，存在才触发此边。
    artifact 为空时：作为默认 fallback 边。
    """
    from_node: str
    to_node: str
    condition: EdgeCondition = EdgeCondition.ALWAYS  # 遗留字段
    condition_expr: Optional[str] = None             # 遗留字段
    artifact: str = ""      # 触发条件文件名，相对于 workspace 根目录
    prompt: str = ""        # 传递给下一个 Agent 的指令（注入为 HumanMessage）


@dataclass
class GraphEntity:
    """Agent 执行图配置"""
    id: str
    name: str
    entry_node: str
    workspace_id: str = ""
    agents: list[AgentEntity] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    def get_agent(self, agent_id: str) -> Optional[AgentEntity]:
        return next((a for a in self.agents if a.id == agent_id), None)

    def get_outgoing_edges(self, agent_id: str) -> list[GraphEdge]:
        return [e for e in self.edges if e.from_node == agent_id]


@dataclass
class LLMProfileEntity:
    """Workspace 内可复用的 LLM 配置。"""
    id: str
    name: str
    provider: LLMProvider
    model: str
    base_url: str = ""
    api_key: str = ""


@dataclass
class CodexConnectionEntity:
    """基于 ChatGPT 登录态的 Codex 连接。"""
    id: str
    name: str
    provider: LLMProvider = LLMProvider.OPENAI_CODEX
    auth_mode: str = "chatgpt_codex_login"
    account_label: str = ""
    status: str = "disconnected"
    credential_ref: str = ""
    last_verified_at: str = ""
    install_status: str = "unknown"
    install_path: str = ""
    login_status: str = "unknown"
    last_checked_at: str = ""
    last_error: str = ""
    cli_version: str = ""
    os_family: str = ""


@dataclass
class PageAuthConfigEntity:
    """页面访问 AK/SK 登录配置。"""
    enabled: bool = False
    access_key: str = ""
    secret_key: str = ""
    token_ttl_seconds: int = 24 * 60 * 60


@dataclass
class GlobalSettingsEntity:
    """全局共享设置：当前主要承载 Provider / LLM 配置。"""
    llm_profiles: list[LLMProfileEntity] = field(default_factory=list)
    codex_connections: list[CodexConnectionEntity] = field(default_factory=list)
    page_auth: PageAuthConfigEntity = field(default_factory=PageAuthConfigEntity)


@dataclass
class ChatMessageEntity:
    """会话中的单条消息或事件。"""
    id: str
    role: str
    kind: str
    content: str
    created_at: str
    actor_id: str = ""
    actor_name: str = ""
    node: str = ""
    session_round: int = 0


@dataclass
class MemoryItemEntity:
    """结构化会话记忆。"""
    id: str
    category: str
    content: str
    confidence: float
    source_message_ids: list[str] = field(default_factory=list)
    updated_at: str = ""


@dataclass
class ChatSessionEntity:
    """Workspace 下的一条会话线程。"""
    id: str
    title: str
    created_at: str
    updated_at: str
    status: str = "idle"
    message_count: int = 0
    summary: str = ""
    memory_items: list[MemoryItemEntity] = field(default_factory=list)
    messages: list[ChatMessageEntity] = field(default_factory=list)


@dataclass
class WorkspaceEntity:
    """
    运行时 Workspace：
    - work_dir: 根目录（如 ~/projects/），Agent 各自在子目录中工作
    - default_*: 新建图/节点时的默认 LLM 配置，节点可单独覆盖
    """
    id: str
    name: str
    work_dir: str                           # 根目录，支持 ~ 展开
    kind: WorkspaceKind = WorkspaceKind.WORKSPACE
    dir_name: str = ""
    default_provider: LLMProvider = LLMProvider.ANTHROPIC
    default_model: str = "claude-sonnet-4-6"
    default_base_url: str = ""              # openai_compat 时必填
    default_api_key: str = ""              # 留空则用环境变量
    llm_profiles: list[LLMProfileEntity] = field(default_factory=list)
    codex_connections: list[CodexConnectionEntity] = field(default_factory=list)
    coordinator: Optional[AgentEntity] = None
    workers: list[AgentEntity] = field(default_factory=list)
    sessions: list[ChatSessionEntity] = field(default_factory=list)
