export const PROVIDERS = [
  { value: 'anthropic', label: 'Anthropic (Claude)' },
  { value: 'openai', label: 'OpenAI (GPT)' },
  { value: 'openai_compat', label: '兼容 OpenAI 协议' },
]

export const PRESET_MODELS = {
  anthropic: ['claude-sonnet-4-6', 'claude-opus-4-6'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
}

export const DEFAULT_CODEX_MODEL = ''
export const DEFAULT_CODEX_MODEL_PLACEHOLDER = '留空则使用 Codex CLI 默认模型'
export const MODEL_RUNTIME_OPTIONS = [
  { value: 'llm', label: 'LLM' },
  { value: 'codex', label: 'Codex' },
]

export function buildProviderName(model = '', baseUrl = '') {
  const normalizedModel = String(model || '').trim()
  const normalizedBaseUrl = String(baseUrl || '').trim()
  if (normalizedModel && normalizedBaseUrl) {
    return `${normalizedModel} + ${normalizedBaseUrl}`
  }
  return normalizedModel || normalizedBaseUrl || '新 API Provider'
}

export function getDefaultLlmProfile(workspace) {
  return workspace?.llm_profiles?.[0] ?? null
}

export function findLlmProfile(workspace, profileId) {
  if (!profileId) return null
  return workspace?.llm_profiles?.find((item) => item.id === profileId) ?? null
}

export function resolveRuntimeType(agent) {
  return agent?.provider === 'openai_codex' ? 'codex' : 'llm'
}

// 默认 Git 工作流配置
export const DEFAULT_GIT_WORKFLOW = {
  enabled: false,
  baseBranch: 'main',
  featureBranchPrefix: 'feature/',
  autoCreateBranch: true,
  autoCommit: true,
  commitMessageTemplate: '[Agent] {{task_name}}',
  prTitleTemplate: '[Agent] {{task_name}}',
  prBodyTemplate: '## 任务描述\n{{task_description}}\n\n## 变更内容\n- 由 Agent 自动生成\n',
  autoCreatePR: false,
}

export function emptyAgent(defaults, role) {
  const isChat = defaults?.kind === 'chat'
  const defaultProfile = getDefaultLlmProfile(defaults)
  const isCoordinator = role === 'coordinator'
  const agent = {
    id: `${role}_${Date.now()}`,
    name: isCoordinator ? (isChat ? '单聊助手' : '主控智能体') : '新 Worker',
    provider: defaultProfile?.provider ?? 'anthropic',
    model: defaultProfile?.model ?? 'claude-sonnet-4-6',
    system_prompt: isCoordinator
      ? (
        isChat
          ? '你是当前单聊目录中的长期助手。需要结合该目录下的历史会话摘要、结构化记忆和当前用户消息，连续地完成对话。如果需要产出文件或中间结果，统一写入当前目录或其子目录，并明确告知路径。不要虚构已执行的操作；工具不足时直接说明。'
          : '你是当前 Workspace 的主控智能体，负责统筹整个任务执行流程。先理解用户目标，再判断需要哪些 Worker 参与。将任务拆成清晰、可执行的子任务，并为每个 Worker 指定目标、输入、输出和完成标准。共享交接物统一写入当前 Workspace 的 shared/ 目录，例如 workspace/<workspace_name>/shared/；不要把 Worker 私有过程文件当成默认交接物。避免角色越权，例如产品类 Worker 不直接产出研发最终实现。最后汇总关键结果、交付物路径和最终结论。'
      )
      : '你是当前 Worker，请只完成分配给你的子任务。需要交接给其他角色的共享产物，统一写入当前 Workspace 的 shared/ 目录，例如 workspace/<workspace_name>/shared/；你的私有过程文件保留在自己的工作目录中。不要越权完成其他角色的最终职责。',
    temperature: 0.7,
    max_tokens: 4096,
    tools: [],
    llm_profile_id: defaultProfile?.id ?? '',
    codex_connection_id: '',
    base_url: defaultProfile?.base_url ?? '',
    api_key: '',
    work_subdir: isCoordinator ? (isChat ? '' : 'coordinator') : '',
    order: 0,
  }

  // Coordinator 非 chat 类型添加 git_workflow 配置
  if (isCoordinator && !isChat) {
    agent.git_workflow = { ...DEFAULT_GIT_WORKFLOW }
  }

  return agent
}

export function sortWorkers(items = []) {
  return [...items].sort((a, b) => {
    const aOrder = a.order > 0 ? a.order : Number.MAX_SAFE_INTEGER
    const bOrder = b.order > 0 ? b.order : Number.MAX_SAFE_INTEGER
    return aOrder - bOrder
  }).map((item, index) => ({ ...item, order: index + 1 }))
}

export function normalizeWorkerOrder(items = []) {
  return items.map((item, index) => ({ ...item, order: index + 1 }))
}

export function normalizeAgentForRuntime(agent, workspace) {
  if (agent.provider === 'openai_codex') {
    return {
      ...agent,
      llm_profile_id: '',
      base_url: '',
      api_key: '',
    }
  }
  const profile = findLlmProfile(workspace, agent.llm_profile_id)
  if (profile) {
    return {
      ...agent,
      provider: profile.provider,
      model: profile.model,
      base_url: profile.base_url ?? '',
      codex_connection_id: '',
    }
  }
  return {
    ...agent,
    codex_connection_id: '',
  }
}

export function normalizeAgentForWorkspace(agent, workspace, role) {
  if (workspace?.kind === 'chat' && role === 'coordinator') {
    return {
      ...agent,
      work_subdir: '',
    }
  }
  return agent
}

export function applyRuntimeSelection(values, workspace, runtimeTypeHint = '') {
  const runtimeType = runtimeTypeHint || values.runtime_type || 'llm'
  if (runtimeType === 'codex') {
    return {
      ...values,
      provider: 'openai_codex',
      llm_profile_id: '',
      model: String(values.model ?? '').trim(),
      base_url: '',
      api_key: '',
    }
  }

  const profile = findLlmProfile(workspace, values.llm_profile_id)
  if (profile) {
    return {
      ...values,
      provider: profile.provider,
      model: profile.model,
      base_url: profile.base_url ?? '',
      api_key: String(values.api_key ?? '').trim(),
    }
  }

  return {
    ...values,
    provider: values.provider || 'anthropic',
    model: String(values.model ?? '').trim(),
    base_url: String(values.base_url ?? '').trim(),
    api_key: String(values.api_key ?? '').trim(),
  }
}

export function resolveLlmDisplay(agent, workspace) {
  const profile = findLlmProfile(workspace, agent?.llm_profile_id)
  if (profile) {
    return profile.name || buildProviderName(profile.model, profile.base_url)
  }
  return agent?.model || '-'
}

export function validateLlmBinding(agent, workspace) {
  if (!agent || agent.provider === 'openai_codex') return null
  if (agent.llm_profile_id) return null
  if (!workspace?.llm_profiles?.length) {
    return '请先在全局模型连接中添加至少一个 API Provider'
  }
  return `${agent.name || '当前角色'} 尚未绑定 API Provider`
}
