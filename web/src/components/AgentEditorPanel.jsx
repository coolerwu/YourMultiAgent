import { Alert, Button, Card, Checkbox, Form, Input, InputNumber, Modal, Select, Space, Tag, Typography, message, Collapse } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { graphApi } from '../utils/graphApi'
import {
  applyRuntimeSelection,
  DEFAULT_CODEX_MODEL,
  DEFAULT_CODEX_MODEL_PLACEHOLDER,
  DEFAULT_GIT_WORKFLOW,
  findLlmProfile,
  getDefaultLlmProfile,
  MODEL_RUNTIME_OPTIONS,
  normalizeAgentForRuntime,
  normalizeAgentForWorkspace,
  resolveRuntimeType,
} from './agentEditorUtils'

const { Panel } = Collapse

const { Option } = Select
const { Text } = Typography

function buildPanelTitle(role, workspace) {
  if (role === 'coordinator') {
    return workspace?.kind === 'chat' ? '单聊助手' : '主控智能体'
  }
  return 'Worker 编辑器'
}

// 按类别分组工具
function groupCapabilitiesByCategory(capabilities = []) {
  const groups = {}
  capabilities.forEach((cap) => {
    let category = '其他'
    if (cap.name.startsWith('git_')) category = 'Git'
    else if (cap.name.startsWith('gh_')) category = 'GitHub'
    else if (cap.name.startsWith('browser_')) category = '浏览器'
    else if (cap.name.startsWith('http_')) category = 'HTTP'
    else if (['read_file', 'write_file', 'list_dir'].includes(cap.name)) category = '文件'
    else if (['run_command'].includes(cap.name)) category = '命令'

    if (!groups[category]) groups[category] = []
    groups[category].push(cap)
  })
  return Object.entries(groups)
}

// 获取工具类别标签
function getCapabilityTag(capName) {
  if (capName.startsWith('git_')) return { color: 'blue', text: 'Git' }
  if (capName.startsWith('gh_')) return { color: 'black', text: 'GitHub' }
  if (capName.startsWith('browser_')) return { color: 'purple', text: 'Browser' }
  if (capName.startsWith('http_')) return { color: 'cyan', text: 'HTTP' }
  if (['read_file', 'write_file', 'list_dir', 'delete_file', 'delete_dir'].includes(capName)) return { color: 'green', text: '文件' }
  if (['run_command'].includes(capName)) return { color: 'orange', text: '命令' }
  return null
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
  const llmProfiles = workspace?.llm_profiles ?? []
  const normalizedAgent = useMemo(
    () => normalizeAgentForWorkspace(normalizeAgentForRuntime(agent, workspace), workspace, role),
    [agent, role, workspace],
  )

  // Git 工作流配置（仅 Coordinator 显示）
  const gitWorkflow = useMemo(() => {
    if (role !== 'coordinator') return null
    return normalizedAgent?.git_workflow ?? DEFAULT_GIT_WORKFLOW
  }, [normalizedAgent, role])

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

  const handleGitWorkflowChange = (updates) => {
    const nextWorkflow = { ...gitWorkflow, ...updates }
    emitChange({
      ...form.getFieldsValue(true),
      git_workflow: nextWorkflow,
    })
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
        provider: values.provider ?? 'anthropic',
        model: values.model ?? '',
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
                  const updates = {
                    provider: 'openai_codex',
                    model: DEFAULT_CODEX_MODEL,
                    llm_profile_id: '',
                    base_url: '',
                    api_key: '',
                  }
                  form.setFieldsValue(updates)
                  emitChange({ ...form.getFieldsValue(true), runtime_type: value, ...updates })
                  return
                }
                const defaultProfile = getDefaultLlmProfile(workspace)
                const updates = {
                  provider: defaultProfile?.provider ?? 'anthropic',
                  model: defaultProfile?.model ?? '',
                  base_url: defaultProfile?.base_url ?? '',
                  codex_connection_id: '',
                  llm_profile_id: defaultProfile?.id ?? '',
                }
                form.setFieldsValue(updates)
                emitChange({ ...form.getFieldsValue(true), runtime_type: value, ...updates })
              }}
            />
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(prev, cur) => (
            prev.runtime_type !== cur.runtime_type
            || prev.codex_connection_id !== cur.codex_connection_id
            || prev.llm_profile_id !== cur.llm_profile_id
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
              const selectedProfile = findLlmProfile(workspace, getFieldValue('llm_profile_id'))
              return (
                <>
                  <Form.Item name="llm_profile_id" label="API Provider" rules={[{ required: true, message: '请选择 API Provider' }]}>
                    <Select
                      placeholder={llmProfiles.length ? '选择共享 API Provider' : '当前还没有 API Provider'}
                      onChange={(profileId) => {
                        const profile = findLlmProfile(workspace, profileId)
                        if (!profile) return
                        const updates = {
                          provider: profile.provider,
                          model: profile.model,
                          base_url: profile.base_url ?? '',
                          api_key: '',
                        }
                        form.setFieldsValue(updates)
                        // 触发父组件更新，确保变更被保存
                        emitChange({
                          ...form.getFieldsValue(true),
                          llm_profile_id: profileId,
                          ...updates,
                        })
                      }}
                    >
                      {llmProfiles.map((profile) => <Option key={profile.id} value={profile.id}>{profile.name}</Option>)}
                    </Select>
                  </Form.Item>
                  {llmProfiles.length === 0 ? (
                    <Alert
                      type="warning"
                      showIcon
                      style={{ marginBottom: 16 }}
                      message="当前还没有 API Provider"
                      description="请先到“全局模型连接 -> API Providers”里新增至少一个 Provider，再回来绑定当前角色。"
                    />
                  ) : null}
                  {selectedProfile ? (
                    <Alert
                      type="info"
                      showIcon
                      style={{ marginBottom: 16 }}
                      message={selectedProfile.name}
                      description={`模型：${selectedProfile.model || '-'}；URL：${selectedProfile.base_url || '官方默认入口'}`}
                    />
                  ) : null}
                </>
              )
            }}
          </Form.Item>
          <Form.Item name="provider" hidden><Input /></Form.Item>
          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.runtime_type !== cur.runtime_type}>
            {({ getFieldValue }) => (
              getFieldValue('runtime_type') !== 'codex' ? <Form.Item name="model" hidden><Input /></Form.Item> : null
            )}
          </Form.Item>
          <Form.Item name="base_url" hidden><Input /></Form.Item>
          <Form.Item name="api_key" hidden><Input /></Form.Item>
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
          <Form.Item name="temperature" label="Temperature" initialValue={0.7}>
            <InputNumber min={0} max={2} step={0.1} style={{ width: 120 }} />
          </Form.Item>
          <Form.Item name="tools" label="工具">
            <Select
              mode="multiple"
              style={{ width: '100%' }}
              placeholder="选择允许使用的工具"
              dropdownStyle={{ minWidth: 400 }}
              listHeight={400}
              maxTagCount={5}
              maxTagTextLength={20}
              filterOption={(input, option) =>
                option?.value?.toLowerCase().includes(input.toLowerCase()) ||
                option?.capDescription?.toLowerCase().includes(input.toLowerCase())
              }
              options={groupCapabilitiesByCategory(capabilities).flatMap(([category, caps]) => [
                { label: <span style={{ fontWeight: 'bold', color: '#999' }}>—— {category} ——</span>, value: `__group_${category}`, disabled: true },
                ...caps.map((cap) => ({
                  value: cap.name,
                  capDescription: cap.description,
                  label: (
                    <Space size={8}>
                      {getCapabilityTag(cap.name) && (
                        <Tag color={getCapabilityTag(cap.name).color} style={{ margin: 0, fontSize: 11 }}>
                          {getCapabilityTag(cap.name).text}
                        </Tag>
                      )}
                      <span>{cap.name}</span>
                      <span style={{ color: '#999', fontSize: 12 }}>{cap.description}</span>
                    </Space>
                  ),
                })),
              ])}
            />
          </Form.Item>
        </Form>

        {/* Git 工作流配置 - 仅 Coordinator 显示 */}
        {role === 'coordinator' && workspace?.kind !== 'chat' && gitWorkflow && (
          <Card
            title="Git 工作流"
            size="small"
            style={{ marginTop: 16 }}
            extra={
              <Checkbox
                checked={gitWorkflow.enabled}
                onChange={(e) => handleGitWorkflowChange({ enabled: e.target.checked })}
              >
                启用
              </Checkbox>
            }
          >
            <Collapse ghost activeKey={gitWorkflow.enabled ? ['git-workflow'] : []}>
              <Panel key="git-workflow" header={null} showArrow={false}>
                <Space direction="vertical" style={{ width: '100%' }} size={12}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>基础分支</Text>
                      <Input
                        value={gitWorkflow.baseBranch}
                        onChange={(e) => handleGitWorkflowChange({ baseBranch: e.target.value })}
                        placeholder="main 或 master"
                        size="small"
                      />
                    </div>
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>功能分支前缀</Text>
                      <Input
                        value={gitWorkflow.featureBranchPrefix}
                        onChange={(e) => handleGitWorkflowChange({ featureBranchPrefix: e.target.value })}
                        placeholder="feature/"
                        size="small"
                      />
                    </div>
                  </div>

                  <Space size={16}>
                    <Checkbox
                      checked={gitWorkflow.autoCreateBranch}
                      onChange={(e) => handleGitWorkflowChange({ autoCreateBranch: e.target.checked })}
                    >
                      自动创建分支
                    </Checkbox>
                    <Checkbox
                      checked={gitWorkflow.autoCommit}
                      onChange={(e) => handleGitWorkflowChange({ autoCommit: e.target.checked })}
                    >
                      自动提交
                    </Checkbox>
                    <Checkbox
                      checked={gitWorkflow.autoCreatePR}
                      onChange={(e) => handleGitWorkflowChange({ autoCreatePR: e.target.checked })}
                    >
                      自动创建 PR
                    </Checkbox>
                  </Space>

                  {gitWorkflow.autoCommit && (
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>提交信息模板</Text>
                      <Input
                        value={gitWorkflow.commitMessageTemplate}
                        onChange={(e) => handleGitWorkflowChange({ commitMessageTemplate: e.target.value })}
                        placeholder="[Agent] {{task_name}}"
                        size="small"
                      />
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        可用变量: {'{{'}task_name{'}}'}, {'{{'}task_description{'}}'}
                      </Text>
                    </div>
                  )}

                  {gitWorkflow.autoCreatePR && (
                    <>
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>PR 标题模板</Text>
                        <Input
                          value={gitWorkflow.prTitleTemplate}
                          onChange={(e) => handleGitWorkflowChange({ prTitleTemplate: e.target.value })}
                          placeholder="[Agent] {{task_name}}"
                          size="small"
                        />
                      </div>
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>PR 描述模板</Text>
                        <Input.TextArea
                          value={gitWorkflow.prBodyTemplate}
                          onChange={(e) => handleGitWorkflowChange({ prBodyTemplate: e.target.value })}
                          placeholder="## 任务描述\n{{task_description}}\n\n## 变更内容\n由 Agent 自动生成"
                          rows={4}
                          size="small"
                        />
                      </div>
                    </>
                  )}

                  <Alert
                    type="info"
                    showIcon
                    message="工作流说明"
                    description={
                      <Space direction="vertical" size={4}>
                        <Text style={{ fontSize: 12 }}>1. 开始时自动从基础分支创建功能分支</Text>
                        <Text style={{ fontSize: 12 }}>2. 开发完成后自动提交更改</Text>
                        <Text style={{ fontSize: 12 }}>3. 推送到远程仓库</Text>
                        <Text style={{ fontSize: 12 }}>4. 自动创建 Pull Request（可选）</Text>
                      </Space>
                    }
                  />
                </Space>
              </Panel>
            </Collapse>
          </Card>
        )}
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
