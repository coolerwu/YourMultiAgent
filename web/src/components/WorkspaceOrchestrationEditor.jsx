import { ArrowDownOutlined, ArrowUpOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from 'antd'
import { useEffect, useState } from 'react'
import { graphApi, workerApi } from '../utils/graphApi'
import { workspaceApi } from '../utils/workspaceApi'

const { Text } = Typography
const { Option } = Select

const PROVIDERS = [
  { value: 'anthropic', label: 'Anthropic (Claude)' },
  { value: 'openai', label: 'OpenAI (GPT)' },
  { value: 'openai_compat', label: '兼容 OpenAI 协议' },
]

const PRESET_MODELS = {
  anthropic: ['claude-sonnet-4-6', 'claude-opus-4-6'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
}
const DEFAULT_CODEX_MODEL = ''
const DEFAULT_CODEX_MODEL_PLACEHOLDER = '留空则使用 Codex CLI 默认模型'
const MODEL_RUNTIME_OPTIONS = [
  { value: 'llm', label: 'LLM' },
  { value: 'codex', label: 'Codex' },
]

function resolveLlmProvider(workspace, currentProvider = '') {
  const workspaceProvider = workspace?.default_provider
  if (PROVIDERS.some((item) => item.value === workspaceProvider)) {
    return workspaceProvider
  }
  if (PROVIDERS.some((item) => item.value === currentProvider)) {
    return currentProvider
  }
  return 'openai_compat'
}

function resolveLlmModel(provider, workspace, currentModel = '') {
  const model = String(currentModel || '').trim()
  if (model) return model
  const workspaceModel = String(workspace?.default_model || '').trim()
  if (workspace?.default_provider === provider && workspaceModel) {
    return workspaceModel
  }
  if (provider === 'anthropic') return PRESET_MODELS.anthropic[0]
  if (provider === 'openai') return PRESET_MODELS.openai[0]
  return workspaceModel || 'deepseek-reasoner'
}

function emptyAgent(defaults, role) {
  const isChat = defaults?.kind === 'chat'
  return {
    id: `${role}_${Date.now()}`,
    name: role === 'coordinator' ? (isChat ? '单聊助手' : '主控智能体') : '新 Worker',
    provider: defaults?.default_provider ?? 'anthropic',
    model: defaults?.default_model ?? 'claude-sonnet-4-6',
    system_prompt: role === 'coordinator'
      ? (
        isChat
          ? '你是当前单聊目录中的长期助手。需要结合该目录下的历史会话摘要、结构化记忆和当前用户消息，连续地完成对话。如果需要产出文件或中间结果，统一写入当前目录或其子目录，并明确告知路径。不要虚构已执行的操作；工具不足时直接说明。'
          : '你是当前 Workspace 的主控智能体，负责统筹整个任务执行流程。先理解用户目标，再判断需要哪些 Worker 参与。将任务拆成清晰、可执行的子任务，并为每个 Worker 指定目标、输入、输出和完成标准。共享交接物统一写入当前 Workspace 的 shared/ 目录，例如 workspace/<workspace_name>/shared/；不要把 Worker 私有过程文件当成默认交接物。避免角色越权，例如产品类 Worker 不直接产出研发最终实现。最后汇总关键结果、交付物路径和最终结论。'
      )
      : '你是当前 Worker，请只完成分配给你的子任务。需要交接给其他角色的共享产物，统一写入当前 Workspace 的 shared/ 目录，例如 workspace/<workspace_name>/shared/；你的私有过程文件保留在自己的工作目录中。不要越权完成其他角色的最终职责。',
    temperature: 0.7,
    max_tokens: 4096,
    tools: [],
    llm_profile_id: '',
    codex_connection_id: '',
    base_url: '',
    api_key: '',
    work_subdir: role === 'coordinator' ? (isChat ? '' : 'coordinator') : '',
    order: 0,
  }
}

function sortWorkers(items = []) {
  return [...items].sort((a, b) => {
    const aOrder = a.order > 0 ? a.order : Number.MAX_SAFE_INTEGER
    const bOrder = b.order > 0 ? b.order : Number.MAX_SAFE_INTEGER
    return aOrder - bOrder
  }).map((item, index) => ({ ...item, order: index + 1 }))
}

function normalizeWorkerOrder(items = []) {
  return items.map((item, index) => ({ ...item, order: index + 1 }))
}

function resolveRuntimeType(agent) {
  return agent?.provider === 'openai_codex' ? 'codex' : 'llm'
}

function normalizeAgentForRuntime(agent, workspace) {
  if (agent.provider === 'openai_codex') {
    return {
      ...agent,
      llm_profile_id: '',
      base_url: '',
      api_key: '',
    }
  }
  const provider = resolveLlmProvider(workspace, agent.provider)
  return {
    ...agent,
    provider,
    model: resolveLlmModel(provider, workspace, agent.model),
    codex_connection_id: '',
    llm_profile_id: '',
  }
}

function normalizeAgentForWorkspace(agent, workspace, role) {
  if (workspace?.kind === 'chat' && role === 'coordinator') {
    return {
      ...agent,
      work_subdir: '',
    }
  }
  return agent
}

export default function WorkspaceOrchestrationEditor({ workspace, onSaved }) {
  const isChat = workspace?.kind === 'chat'
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [capabilities, setCapabilities] = useState([])
  const [coordinator, setCoordinator] = useState(emptyAgent(workspace, 'coordinator'))
  const [workers, setWorkers] = useState([])
  const [editing, setEditing] = useState({ open: false, role: 'worker', index: -1 })
  const [generatingWorker, setGeneratingWorker] = useState(false)
  const [workerGenerator, setWorkerGenerator] = useState({
    open: false,
    goal: '',
    reason: '',
  })
  const [optimizingPrompt, setOptimizingPrompt] = useState(false)
  const [promptOptimizer, setPromptOptimizer] = useState({
    open: false,
    goal: '润色当前 Prompt，让表达更清晰、更稳定',
    optimizedPrompt: '',
    reason: '',
  })
  const [form] = Form.useForm()
  const codexConnections = workspace?.codex_connections ?? []

  useEffect(() => {
    workerApi.listCapabilities().then(setCapabilities).catch(() => {})
  }, [])

  useEffect(() => {
    if (!workspace?.id) return
    setLoading(true)
    workspaceApi.getOrchestration(workspace.id)
      .then((result) => {
        setCoordinator(result.coordinator ?? emptyAgent(workspace, 'coordinator'))
        setWorkers(sortWorkers(result.workers ?? []))
      })
      .catch((e) => message.error(e.message))
      .finally(() => setLoading(false))
  }, [workspace])

  const openEditor = (role, index = -1) => {
    const target = role === 'coordinator'
      ? coordinator
      : workers[index] ?? emptyAgent(workspace, 'worker')
    const normalizedTarget = normalizeAgentForWorkspace(
      normalizeAgentForRuntime(target, workspace),
      workspace,
      role,
    )
    form.setFieldsValue({
      ...normalizedTarget,
      runtime_type: resolveRuntimeType(normalizedTarget),
    })
    setEditing({ open: true, role, index })
  }

  const saveAgent = async () => {
    const values = await form.validateFields()
    const baseAgent = editing.role === 'coordinator'
      ? coordinator
      : workers[editing.index] ?? emptyAgent(workspace, 'worker')
    const nextAgent = normalizeAgentForWorkspace(normalizeAgentForRuntime({
      ...baseAgent,
      ...values,
    }, workspace), workspace, editing.role)
    delete nextAgent.runtime_type
    if (editing.role === 'coordinator') {
      setCoordinator(nextAgent)
    } else if (editing.index >= 0) {
      setWorkers((prev) => normalizeWorkerOrder(prev.map((item, index) => (
        index === editing.index ? { ...nextAgent, order: item.order } : item
      ))))
    } else {
      setWorkers((prev) => normalizeWorkerOrder([
        ...prev,
        { ...nextAgent, id: nextAgent.id || `worker_${Date.now()}`, order: prev.length + 1 },
      ]))
    }
    setEditing({ open: false, role: 'worker', index: -1 })
  }

  const openWorkerGenerator = () => {
    setWorkerGenerator({ open: true, goal: '', reason: '' })
  }

  const generateWorker = async () => {
    if (!workerGenerator.goal.trim()) {
      message.warning('请先描述想要的 Worker')
      return
    }
    setGeneratingWorker(true)
    try {
      const result = await graphApi.generateWorker({
        workspace_id: workspace?.id ?? '',
        user_goal: workerGenerator.goal.trim(),
        coordinator_name: coordinator.name,
        coordinator_prompt: coordinator.system_prompt,
        existing_worker_names: workers.map((item) => item.name),
        available_tools: capabilities.map((item) => item.name),
        provider: workspace?.default_provider ?? coordinator.provider ?? 'anthropic',
        model: workspace?.default_model ?? coordinator.model ?? 'claude-sonnet-4-6',
        llm_profile_id: coordinator.llm_profile_id ?? '',
        codex_connection_id: coordinator.codex_connection_id ?? '',
        base_url: coordinator.base_url ?? '',
        api_key: coordinator.api_key ?? '',
      })
      const generatedWorkers = (result.workers ?? []).map((item, index) => ({
        ...item,
        id: item.id || `worker_${Date.now()}_${index}`,
        order: workers.length + index + 1,
      }))
      setWorkers((prev) => normalizeWorkerOrder([...prev, ...generatedWorkers]))
      setWorkerGenerator({
        open: false,
        goal: '',
        reason: result.reason ?? '',
      })
      message.success(result.reason || `已生成 ${generatedWorkers.length} 个 Worker 草稿`)
    } catch (e) {
      message.error(e.message)
    } finally {
      setGeneratingWorker(false)
    }
  }

  const persist = async () => {
    if (!workspace?.id) return
    setSaving(true)
    try {
      const nextWorkers = normalizeWorkerOrder(workers)
      setWorkers(nextWorkers)
      await workspaceApi.updateOrchestration(workspace.id, {
        coordinator: { ...coordinator, order: 0 },
        workers: nextWorkers,
      })
      message.success('编排配置已保存')
      onSaved?.()
    } catch (e) {
      message.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  const openPromptOptimizer = async () => {
    await form.validateFields(['name'])
    setPromptOptimizer({
      open: true,
      goal: '润色当前 Prompt，让表达更清晰、更稳定',
      optimizedPrompt: '',
      reason: '',
    })
  }

  const optimizePrompt = async () => {
    const values = form.getFieldsValue()
    setOptimizingPrompt(true)
    try {
      const result = await graphApi.optimizePrompt({
        name: values.name,
        system_prompt: values.system_prompt ?? '',
        goal: promptOptimizer.goal,
        workspace_id: workspace?.id ?? '',
        provider: values.provider ?? workspace?.default_provider ?? 'anthropic',
        model: values.model ?? workspace?.default_model ?? 'claude-sonnet-4-6',
        temperature: 0.2,
        max_tokens: values.max_tokens ?? 4096,
        tools: values.tools ?? [],
        llm_profile_id: values.llm_profile_id ?? '',
        codex_connection_id: values.codex_connection_id ?? '',
        base_url: values.base_url ?? '',
        api_key: values.api_key ?? '',
      })
      setPromptOptimizer((prev) => ({
        ...prev,
        optimizedPrompt: result.optimized_prompt ?? '',
        reason: result.reason ?? '',
      }))
    } catch (e) {
      message.error(e.message)
    } finally {
      setOptimizingPrompt(false)
    }
  }

  const moveWorker = (index, direction) => {
    setWorkers((prev) => {
      const next = [...prev]
      const target = index + direction
      if (target < 0 || target >= next.length) return prev
      ;[next[index], next[target]] = [next[target], next[index]]
      return normalizeWorkerOrder(next)
    })
  }

  return (
    <div style={{ padding: 20 }}>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Card
          loading={loading}
          title={isChat ? '单聊助手' : '主控智能体'}
          extra={<Button onClick={() => openEditor('coordinator')}>编辑</Button>}
        >
          <Space direction="vertical" size={6} style={{ width: '100%' }}>
            <Text strong>{coordinator.name}</Text>
            <Text type="secondary">{coordinator.model}</Text>
            <Text type="secondary">{isChat ? '当前目录根' : (coordinator.work_subdir || 'coordinator')}</Text>
            <Text style={{ whiteSpace: 'pre-wrap' }}>{coordinator.system_prompt}</Text>
          </Space>
        </Card>

        {!isChat ? (
          <>
            <Card
              loading={loading}
              title="Worker 角色"
              extra={(
                <Space>
                  <Button onClick={openWorkerGenerator}>AI 生成</Button>
                  <Button icon={<PlusOutlined />} onClick={() => openEditor('worker')}>新增 Worker</Button>
                </Space>
              )}
            >
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                {workers.length === 0 && <Text type="secondary">当前还没有 Worker</Text>}
                {workers.map((worker, index) => (
                  <Card
                    key={worker.id}
                    size="small"
                    title={`#${worker.order || index + 1} ${worker.name}`}
                    extra={(
                      <Space>
                        <Button size="small" icon={<ArrowUpOutlined />} disabled={index === 0} onClick={() => moveWorker(index, -1)} />
                        <Button size="small" icon={<ArrowDownOutlined />} disabled={index === workers.length - 1} onClick={() => moveWorker(index, 1)} />
                        <Button size="small" onClick={() => openEditor('worker', index)}>编辑</Button>
                        <Button
                          size="small"
                          danger
                          icon={<DeleteOutlined />}
                          onClick={() => setWorkers((prev) => normalizeWorkerOrder(prev.filter((_, i) => i !== index)))}
                        />
                      </Space>
                    )}
                  >
                    <Space direction="vertical" size={4}>
                      <Text type="secondary">{worker.model}</Text>
                      <Text type="secondary">目录：{worker.work_subdir || worker.name}</Text>
                      <div>
                        {(worker.tools ?? []).map((tool) => <Tag key={tool}>{tool}</Tag>)}
                      </div>
                    </Space>
                  </Card>
                ))}
              </Space>
            </Card>

            <Card size="small" title="共享约定">
              <Space direction="vertical" size={4}>
                <Text>主控智能体负责拆解任务，并把交接规则明确给 Worker。</Text>
                <Text>共享交接物统一写入当前 Workspace 的 `shared/` 目录，例如 `workspace/&lt;workspace_name&gt;/shared/`。</Text>
                <Text>Worker 私有工作内容写入各自 `work_subdir/` 根目录。</Text>
                <Text>不要把 Worker 私有过程文件当成默认交接物。</Text>
              </Space>
            </Card>
          </>
        ) : null}

        <div>
          <Button type="primary" loading={saving} onClick={persist}>保存编排配置</Button>
        </div>
      </Space>

      <Modal
        title="AI 生成 Worker"
        open={workerGenerator.open}
        onCancel={() => setWorkerGenerator({ open: false, goal: '', reason: '' })}
        onOk={generateWorker}
        confirmLoading={generatingWorker}
        okText="生成 Worker"
      >
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Text type="secondary">
            描述你想新增的一组 Worker 角色，例如“做一个宠物产品页面，需要产品、前端和测试协作”。
          </Text>
          <Input.TextArea
            rows={5}
            value={workerGenerator.goal}
            onChange={(e) => setWorkerGenerator((prev) => ({ ...prev, goal: e.target.value }))}
            placeholder="例如：做一个宠物产品页面，需要拆出产品经理、前端研发、测试 3 个 Worker。"
          />
        </Space>
      </Modal>

      <Modal
        title={editing.role === 'coordinator' ? (isChat ? '编辑单聊助手' : '编辑主控智能体') : '编辑 Worker'}
        open={editing.open}
        onOk={saveAgent}
        onCancel={() => setEditing({ open: false, role: 'worker', index: -1 })}
        width={640}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="id" hidden><Input /></Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="runtime_type" label="模型类型" initialValue="llm" rules={[{ required: true }]}>
            <Select
              options={MODEL_RUNTIME_OPTIONS}
              onChange={(value) => {
                if (value === 'codex') {
                  form.setFieldsValue({
                    provider: 'openai_codex',
                    model: DEFAULT_CODEX_MODEL,
                    llm_profile_id: '',
                    base_url: '',
                    api_key: '',
                  })
                  return
                }
                const nextProvider = resolveLlmProvider(workspace, form.getFieldValue('provider'))
                form.setFieldsValue({
                  provider: nextProvider,
                  model: resolveLlmModel(nextProvider, workspace, form.getFieldValue('model')),
                  codex_connection_id: '',
                  llm_profile_id: '',
                })
              }}
            />
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(prev, cur) => (
            prev.runtime_type !== cur.runtime_type
            || prev.codex_connection_id !== cur.codex_connection_id
            || prev.provider !== cur.provider
          )}>
            {({ getFieldValue }) => {
              const runtimeType = getFieldValue('runtime_type') ?? 'llm'
              if (runtimeType === 'codex') {
                return (
                  <>
                    <Form.Item name="codex_connection_id" label="Codex 登录连接">
                      <Select
                        allowClear
                        placeholder={codexConnections.length ? '选择 Codex 登录连接' : '当前 Workspace 暂无 Codex 登录连接'}
                      >
                        {codexConnections.map((connection) => (
                          <Option key={connection.id} value={connection.id}>{connection.name}</Option>
                        ))}
                      </Select>
                    </Form.Item>
                    <Form.Item
                      name="model"
                      label="Codex 模型"
                      extra="建议留空，直接使用当前 Codex CLI 账号默认可用模型；只有明确知道模型权限时再手动填写"
                    >
                      <Input placeholder={DEFAULT_CODEX_MODEL_PLACEHOLDER} />
                    </Form.Item>
                  </>
                )
              }
              const provider = getFieldValue('provider')
              return (
                <>
                  <Form.Item name="provider" label="Provider" rules={[{ required: true }]}>
                    <Select
                      onChange={(nextProvider) => {
                        const currentModel = form.getFieldValue('model')
                        const presetModels = PRESET_MODELS[nextProvider] ?? []
                        const shouldResetModel = !currentModel || (
                          nextProvider !== 'openai_compat' && !presetModels.includes(currentModel)
                        )
                        if (shouldResetModel) {
                          form.setFieldValue('model', resolveLlmModel(nextProvider, workspace, ''))
                        }
                      }}
                    >
                      {PROVIDERS.map((item) => <Option key={item.value} value={item.value}>{item.label}</Option>)}
                    </Select>
                  </Form.Item>
                  <Form.Item name="model" label="模型" rules={[{ required: true }]}>
                    {provider === 'openai_compat'
                      ? <Input placeholder="例如：deepseek-chat" />
                      : (
                        <Select>
                          {(PRESET_MODELS[provider] ?? []).map((model) => (
                            <Option key={model} value={model}>{model}</Option>
                          ))}
                        </Select>
                      )}
                  </Form.Item>
                </>
              )
            }}
          </Form.Item>
          <Form.Item
            name="system_prompt"
            label={(
              <Space size={8}>
                <span>Prompt</span>
                <Button size="small" onClick={openPromptOptimizer}>AI 优化</Button>
              </Space>
            )}
            rules={[{ required: true }]}
          >
            <Input.TextArea rows={6} />
          </Form.Item>
          {!(isChat && editing.role === 'coordinator') && (
            <Form.Item name="work_subdir" label="工作子目录">
              <Input />
            </Form.Item>
          )}
          <Form.Item name="temperature" label="Temperature">
            <InputNumber min={0} max={2} step={0.1} style={{ width: 120 }} />
          </Form.Item>
          <Form.Item name="tools" label="工具">
            <Select mode="multiple">
              {capabilities.map((cap) => <Option key={cap.name} value={cap.name}>{cap.name}</Option>)}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="AI 优化 Prompt"
        open={promptOptimizer.open}
        onCancel={() => setPromptOptimizer((prev) => ({ ...prev, open: false }))}
        width={680}
        footer={[
          <Button key="cancel" onClick={() => setPromptOptimizer((prev) => ({ ...prev, open: false }))}>关闭</Button>,
          <Button key="optimize" type="primary" loading={optimizingPrompt} onClick={optimizePrompt}>生成建议</Button>,
          <Button
            key="apply"
            type="primary"
            disabled={!promptOptimizer.optimizedPrompt}
            onClick={() => {
              form.setFieldValue('system_prompt', promptOptimizer.optimizedPrompt)
              setPromptOptimizer((prev) => ({ ...prev, open: false }))
            }}
          >
            替换当前 Prompt
          </Button>,
        ]}
      >
        <Space direction="vertical" style={{ width: '100%' }} size={16}>
          <Select
            value={promptOptimizer.goal}
            onChange={(goal) => setPromptOptimizer((prev) => ({ ...prev, goal }))}
            options={[
              { value: '润色当前 Prompt，让表达更清晰、更稳定', label: '润色表达' },
              { value: '增强约束，让任务边界、输出要求和工具使用规则更明确', label: '增强约束' },
              { value: '按当前角色重写 Prompt，让职责、输入输出和协作方式更完整', label: '按角色重写' },
            ]}
          />
          <Input.TextArea rows={10} readOnly value={promptOptimizer.optimizedPrompt} />
          <Input.TextArea rows={3} readOnly value={promptOptimizer.reason} />
        </Space>
      </Modal>
    </div>
  )
}
