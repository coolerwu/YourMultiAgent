import { Button, Card, Form, Input, InputNumber, Modal, Select, Space, Typography, message } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { graphApi } from '../utils/graphApi'
import {
  applyRuntimeSelection,
  DEFAULT_CODEX_MODEL,
  DEFAULT_CODEX_MODEL_PLACEHOLDER,
  MODEL_RUNTIME_OPTIONS,
  normalizeAgentForRuntime,
  normalizeAgentForWorkspace,
  PRESET_MODELS,
  PROVIDERS,
  resolveLlmModel,
  resolveLlmProvider,
  resolveRuntimeType,
} from './agentEditorUtils'

const { Option } = Select
const { Text } = Typography

function buildPanelTitle(role, workspace) {
  if (role === 'coordinator') {
    return workspace?.kind === 'chat' ? '单聊助手' : '主控智能体'
  }
  return 'Worker 编辑器'
}

export default function AgentEditorPanel({
  workspace,
  role,
  agent,
  capabilities,
  codexConnections,
  onChange,
}) {
  const [form] = Form.useForm()
  const [optimizingPrompt, setOptimizingPrompt] = useState(false)
  const [promptOptimizer, setPromptOptimizer] = useState({
    open: false,
    goal: '润色当前 Prompt，让表达更清晰、更稳定',
    optimizedPrompt: '',
    reason: '',
  })

  const panelTitle = useMemo(() => buildPanelTitle(role, workspace), [role, workspace])
  const normalizedAgent = useMemo(
    () => normalizeAgentForWorkspace(normalizeAgentForRuntime(agent, workspace), workspace, role),
    [agent, role, workspace],
  )

  useEffect(() => {
    form.setFieldsValue({
      ...normalizedAgent,
      runtime_type: resolveRuntimeType(normalizedAgent),
    })
  }, [form, normalizedAgent])

  const emitChange = (allValues) => {
    const runtimeType = allValues.runtime_type ?? resolveRuntimeType(normalizedAgent)
    const nextAgent = normalizeAgentForWorkspace(normalizeAgentForRuntime({
      ...normalizedAgent,
      ...applyRuntimeSelection(allValues, workspace, runtimeType),
    }, workspace), workspace, role)
    delete nextAgent.runtime_type
    onChange(nextAgent)
  }

  const openPromptOptimizer = async () => {
    try {
      await form.validateFields(['name'])
    } catch {
      return
    }
    setPromptOptimizer({
      open: true,
      goal: '润色当前 Prompt，让表达更清晰、更稳定',
      optimizedPrompt: '',
      reason: '',
    })
  }

  const optimizePrompt = async () => {
    const values = form.getFieldsValue(true)
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

  const applyOptimizedPrompt = () => {
    const optimizedPrompt = promptOptimizer.optimizedPrompt
    form.setFieldValue('system_prompt', optimizedPrompt)
    emitChange({
      ...form.getFieldsValue(true),
      system_prompt: optimizedPrompt,
    })
    setPromptOptimizer((prev) => ({ ...prev, open: false }))
  }

  return (
    <>
      <Card
        title={panelTitle}
        extra={<Text type="secondary">{role === 'coordinator' && workspace?.kind === 'chat' ? '当前目录根' : agent?.work_subdir || agent?.name || '-'}</Text>}
      >
        <Form
          form={form}
          layout="vertical"
          onValuesChange={(_, allValues) => emitChange(allValues)}
        >
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
            <Input.TextArea rows={10} />
          </Form.Item>
          {!(workspace?.kind === 'chat' && role === 'coordinator') && (
            <Form.Item name="work_subdir" label="工作子目录">
              <Input />
            </Form.Item>
          )}
          <Space size={16} style={{ width: '100%' }} align="start">
            <Form.Item name="temperature" label="Temperature">
              <InputNumber min={0} max={2} step={0.1} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="tools" label="工具" style={{ flex: 1 }}>
              <Select mode="multiple">
                {capabilities.map((cap) => <Option key={cap.name} value={cap.name}>{cap.name}</Option>)}
              </Select>
            </Form.Item>
          </Space>
        </Form>
      </Card>

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
            onClick={applyOptimizedPrompt}
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
    </>
  )
}
