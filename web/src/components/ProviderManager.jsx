/**
 * components/ProviderManager.jsx
 *
 * Provider 配置弹窗：维护全局共享的 API Provider 与 Codex 登录连接。
 */

import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Form, Input, Modal, Select, Space, Tabs, Tag, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { workspaceApi } from '../utils/workspaceApi'

const { Option } = Select
const { Text } = Typography

const PROVIDERS = [
  { value: 'anthropic', label: 'Anthropic (Claude)' },
  { value: 'openai', label: 'OpenAI (GPT)' },
  { value: 'openai_compat', label: '兼容 OpenAI 协议（DeepSeek / Moonshot 等）' },
]

const PRESET_MODELS = {
  anthropic: ['claude-sonnet-4-6', 'claude-opus-4-6', 'claude-haiku-4-5-20251001'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
}

function CodexStatusTag({ status }) {
  if (status === 'connected') return <Tag color="green">已连接</Tag>
  if (status === 'expired') return <Tag color="orange">已过期</Tag>
  return <Tag>未连接</Tag>
}

export default function ProviderManager({ open, onClose, onSaved, embedded = false }) {
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [runtimeSummary, setRuntimeSummary] = useState(null)
  const [runningActionId, setRunningActionId] = useState('')
  const [actionHints, setActionHints] = useState({})

  useEffect(() => {
    if (!embedded && !open) return
    loadSettings()
  }, [open, embedded, form])

  const loadSettings = async () => {
    try {
      const [settings, runtime] = await Promise.all([
        workspaceApi.getProviderSettings(),
        workspaceApi.getCodexRuntimeSummary(),
      ])
      form.setFieldsValue({
        default_provider: settings.default_provider ?? 'anthropic',
        default_model: settings.default_model ?? 'claude-sonnet-4-6',
        default_base_url: settings.default_base_url ?? '',
        default_api_key: settings.default_api_key ?? '',
        llm_profiles: settings.llm_profiles ?? [],
        codex_connections: settings.codex_connections ?? [],
      })
      setRuntimeSummary(runtime)
    } catch (e) {
      message.error(e.message)
    }
  }

  const buildPayload = async () => {
    let vals
    try {
      vals = await form.validateFields()
    } catch {
      return null
    }

    return {
      default_provider: vals.default_provider,
      default_model: vals.default_model,
      default_base_url: vals.default_base_url ?? '',
      default_api_key: vals.default_api_key ?? '',
      llm_profiles: (vals.llm_profiles ?? []).map((profile, index) => ({
        ...profile,
        id: profile.id || `llm_${Date.now()}_${index}`,
      })),
      codex_connections: (vals.codex_connections ?? []).map((connection, index) => ({
        ...connection,
        id: connection.id || `codex_${Date.now()}_${index}`,
        provider: 'openai_codex',
        auth_mode: 'chatgpt_codex_login',
      })),
    }
  }

  const persistSettings = async ({ closeOnSuccess = false, successMessage = '' } = {}) => {
    const payload = await buildPayload()
    if (!payload) return null

    setSaving(true)
    try {
      const saved = await workspaceApi.updateProviderSettings(payload)
      if (successMessage) {
        message.success(successMessage)
      }
      form.setFieldsValue({
        default_provider: saved.default_provider ?? 'anthropic',
        default_model: saved.default_model ?? 'claude-sonnet-4-6',
        default_base_url: saved.default_base_url ?? '',
        default_api_key: saved.default_api_key ?? '',
        llm_profiles: saved.llm_profiles ?? [],
        codex_connections: saved.codex_connections ?? [],
      })
      onSaved?.(saved)
      if (closeOnSuccess) {
        onClose?.()
      }
      return saved
    } catch (e) {
      message.error(e.message)
      return null
    } finally {
      setSaving(false)
    }
  }

  const handleOk = async () => {
    await persistSettings({
      closeOnSuccess: true,
      successMessage: '全局模型连接配置已更新',
    })
  }

  const runCodexAction = async (connectionId, action, fieldIndex) => {
    const targetNamePath = ['codex_connections', fieldIndex, 'name']
    try {
      await form.validateFields([targetNamePath])
    } catch {
      return
    }
    const saved = await persistSettings()
    if (!saved) return
    const savedConnection = (saved.codex_connections ?? []).find((item) => item.id === connectionId)
    const effectiveId = savedConnection?.id || connectionId
    if (!effectiveId) return

    setRunningActionId(`${action}:${effectiveId}`)
    try {
      const result = action === 'check'
        ? await workspaceApi.checkCodexConnection(effectiveId)
        : action === 'install'
          ? await workspaceApi.installCodexConnection(effectiveId)
          : await workspaceApi.loginCodexConnection(effectiveId)
      setActionHints((prev) => ({
        ...prev,
        [effectiveId]: {
          message: result.message,
          manualCommand: result.manual_command ?? '',
          details: result.details ?? '',
        },
      }))
      message.success(result.message)
      await loadSettings()
      onSaved?.()
    } catch (e) {
      message.error(e.message)
    } finally {
      setRunningActionId('')
    }
  }

  const codexConnectionHeader = runtimeSummary ? (
    <Alert
      type="info"
      showIcon
      message={`当前宿主机：${runtimeSummary.os_family || 'unknown'}；Node：${runtimeSummary.node_path ? '已安装' : '未检测到'}；npm：${runtimeSummary.npm_path ? '已安装' : '未检测到'}；Codex：${runtimeSummary.codex_path ? `已安装 (${runtimeSummary.codex_version || 'unknown'})` : '未安装'}`}
    />
  ) : null

  const content = (
    <Form form={form} layout="vertical" style={{ marginTop: embedded ? 0 : 16 }}>
      <Tabs
        items={[
          {
            key: 'api',
            label: 'API Providers',
            children: (
              <>
                <Space size={12} style={{ width: '100%' }} align="start">
                  <Form.Item
                    name="default_provider"
                    label="默认 Provider"
                    rules={[{ required: true }]}
                    style={{ flex: 1 }}
                  >
                    <Select>
                      {PROVIDERS.map((p) => <Option key={p.value} value={p.value}>{p.label}</Option>)}
                    </Select>
                  </Form.Item>

                  <Form.Item
                    noStyle
                    shouldUpdate={(prev, cur) => prev.default_provider !== cur.default_provider}
                  >
                    {({ getFieldValue }) => {
                      const provider = getFieldValue('default_provider')
                      return (
                        <Form.Item
                          name="default_model"
                          label="默认模型"
                          rules={[{ required: true, message: '请输入默认模型' }]}
                          style={{ flex: 1 }}
                        >
                          {provider === 'openai_compat' ? (
                            <Input placeholder="例如：deepseek-chat" />
                          ) : (
                            <Select>
                              {(PRESET_MODELS[provider] ?? []).map((m) => <Option key={m} value={m}>{m}</Option>)}
                            </Select>
                          )}
                        </Form.Item>
                      )
                    }}
                  </Form.Item>
                </Space>

                <Form.Item noStyle shouldUpdate={(prev, cur) => prev.default_provider !== cur.default_provider}>
                  {({ getFieldValue }) =>
                    getFieldValue('default_provider') === 'openai_compat' && (
                      <Form.Item
                        name="default_base_url"
                        label="默认 Base URL"
                        rules={[{ required: true, message: '请输入默认 base_url' }]}
                      >
                        <Input placeholder="例如：https://api.deepseek.com/v1" />
                      </Form.Item>
                    )
                  }
                </Form.Item>

                <Form.Item name="default_api_key" label="默认 API Key（选填）">
                  <Input.Password placeholder="sk-..." />
                </Form.Item>

                <Form.List name="llm_profiles">
                  {(fields, { add, remove }) => (
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                        <div>
                          <div style={{ fontWeight: 600 }}>可复用 API Provider</div>
                          <div style={{ fontSize: 12, color: '#888' }}>
                            所有 Workspace 共享引用；适用于 API Key / Base URL 模式
                          </div>
                        </div>
                        <Button
                          icon={<PlusOutlined />}
                          onClick={() => add({
                            id: '',
                            name: '',
                            provider: 'anthropic',
                            model: 'claude-sonnet-4-6',
                            base_url: '',
                            api_key: '',
                          })}
                        >
                          添加 Provider
                        </Button>
                      </div>

                      {fields.map((field) => (
                        <Card
                          key={field.key}
                          size="small"
                          style={{ marginBottom: 12 }}
                          title={`Provider #${field.name + 1}`}
                          extra={<Button type="text" danger icon={<MinusCircleOutlined />} onClick={() => remove(field.name)} />}
                        >
                          <Form.Item name={[field.name, 'id']} hidden>
                            <Input />
                          </Form.Item>

                          <Form.Item
                            name={[field.name, 'name']}
                            label="名称"
                            rules={[{ required: true, message: '请输入名称' }]}
                          >
                            <Input placeholder="例如：Claude 主力 / DeepSeek 推理 / GPT-4o" />
                          </Form.Item>

                          <Space size={12} style={{ width: '100%' }} align="start">
                            <Form.Item
                              name={[field.name, 'provider']}
                              label="Provider 类型"
                              rules={[{ required: true }]}
                              style={{ flex: 1 }}
                            >
                              <Select>
                                {PROVIDERS.map((p) => <Option key={p.value} value={p.value}>{p.label}</Option>)}
                              </Select>
                            </Form.Item>

                            <Form.Item
                              noStyle
                              shouldUpdate={(prev, cur) =>
                                prev.llm_profiles?.[field.name]?.provider !== cur.llm_profiles?.[field.name]?.provider
                              }
                            >
                              {({ getFieldValue }) => {
                                const provider = getFieldValue(['llm_profiles', field.name, 'provider'])
                                return (
                                  <Form.Item
                                    name={[field.name, 'model']}
                                    label="模型"
                                    rules={[{ required: true, message: '请输入模型' }]}
                                    style={{ flex: 1 }}
                                  >
                                    {provider === 'openai_compat' ? (
                                      <Input placeholder="例如：deepseek-chat" />
                                    ) : (
                                      <Select>
                                        {(PRESET_MODELS[provider] ?? []).map((m) => <Option key={m} value={m}>{m}</Option>)}
                                      </Select>
                                    )}
                                  </Form.Item>
                                )
                              }}
                            </Form.Item>
                          </Space>

                          <Form.Item
                            noStyle
                            shouldUpdate={(prev, cur) =>
                              prev.llm_profiles?.[field.name]?.provider !== cur.llm_profiles?.[field.name]?.provider
                            }
                          >
                            {({ getFieldValue }) =>
                              getFieldValue(['llm_profiles', field.name, 'provider']) === 'openai_compat' && (
                                <Form.Item
                                  name={[field.name, 'base_url']}
                                  label="Base URL"
                                  rules={[{ required: true, message: '请输入 base_url' }]}
                                >
                                  <Input placeholder="例如：https://api.deepseek.com/v1" />
                                </Form.Item>
                              )
                            }
                          </Form.Item>

                          <Form.Item name={[field.name, 'api_key']} label="API Key（选填）">
                            <Input.Password placeholder="sk-..." />
                          </Form.Item>
                        </Card>
                      ))}
                    </div>
                  )}
                </Form.List>
              </>
            ),
          },
            {
              key: 'codex',
              label: 'Codex 登录',
              children: (
              <>
                {codexConnectionHeader}
                <div style={{ height: 12 }} />
                <Form.List name="codex_connections">
                {(fields, { add, remove }) => (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <div>
                        <div style={{ fontWeight: 600 }}>Codex 登录连接</div>
                        <div style={{ fontSize: 12, color: '#888' }}>
                          用于承载 ChatGPT Codex 登录态引用；当前仅完成配置建模，服务端运行时尚未接入真实登录通道
                        </div>
                      </div>
                      <Button
                        icon={<PlusOutlined />}
                        onClick={() => add({
                          id: `codex_${Date.now()}`,
                          name: '',
                          provider: 'openai_codex',
                          auth_mode: 'chatgpt_codex_login',
                          account_label: '',
                          status: 'disconnected',
                          credential_ref: '',
                          last_verified_at: '',
                        })}
                      >
                        添加连接
                      </Button>
                    </div>

                    {fields.map((field) => {
                      const connectionId = form.getFieldValue(['codex_connections', field.name, 'id'])
                      return (
                        <Card
                          key={field.key}
                          size="small"
                          style={{ marginBottom: 12 }}
                          title={`Codex 连接 #${field.name + 1}`}
                          extra={<Button type="text" danger icon={<MinusCircleOutlined />} onClick={() => remove(field.name)} />}
                        >
                          <Form.Item name={[field.name, 'id']} hidden>
                            <Input />
                          </Form.Item>

                          <Form.Item
                            name={[field.name, 'name']}
                            label="连接名称"
                            rules={[{ required: true, message: '请输入连接名称' }]}
                          >
                            <Input placeholder="例如：个人 ChatGPT Codex / 团队 Codex 登录" />
                          </Form.Item>

                          <Space size={12} style={{ width: '100%' }} align="start">
                            <Form.Item label="账号标识" style={{ flex: 1 }}>
                              <Input value={form.getFieldValue(['codex_connections', field.name, 'account_label']) || '-'} readOnly />
                            </Form.Item>
                            <Form.Item label="连接状态" style={{ width: 160 }}>
                              <Input value={form.getFieldValue(['codex_connections', field.name, 'status']) || '未连接'} readOnly />
                            </Form.Item>
                          </Space>

                          <Space size={12} style={{ width: '100%' }} align="start">
                            <Form.Item label="凭据引用" style={{ flex: 1 }}>
                              <Input value={form.getFieldValue(['codex_connections', field.name, 'credential_ref']) || '-'} readOnly />
                            </Form.Item>
                            <Form.Item label="最近校验时间" style={{ flex: 1 }}>
                              <Input value={form.getFieldValue(['codex_connections', field.name, 'last_verified_at']) || '-'} readOnly />
                            </Form.Item>
                          </Space>

                          <Space wrap style={{ marginBottom: 12 }}>
                            <Button
                              size="small"
                              loading={runningActionId === `check:${connectionId}`}
                              onClick={() => runCodexAction(connectionId, 'check', field.name)}
                            >
                              检测环境
                            </Button>
                            <Button
                              size="small"
                              loading={runningActionId === `install:${connectionId}`}
                              onClick={() => runCodexAction(connectionId, 'install', field.name)}
                            >
                              安装 Codex
                            </Button>
                            <Button
                              size="small"
                              loading={runningActionId === `login:${connectionId}`}
                              onClick={() => runCodexAction(connectionId, 'login', field.name)}
                            >
                              登录 Codex
                            </Button>
                          </Space>

                          <Space direction="vertical" size={4} style={{ width: '100%' }}>
                            <Text type="secondary">安装状态：{form.getFieldValue(['codex_connections', field.name, 'install_status']) || 'unknown'}</Text>
                            <Text type="secondary">登录状态：{form.getFieldValue(['codex_connections', field.name, 'login_status']) || 'unknown'}</Text>
                            <Text type="secondary">CLI 版本：{form.getFieldValue(['codex_connections', field.name, 'cli_version']) || '-'}</Text>
                            <Text type="secondary">安装路径：{form.getFieldValue(['codex_connections', field.name, 'install_path']) || '-'}</Text>
                            <Text type="secondary">最近检查：{form.getFieldValue(['codex_connections', field.name, 'last_checked_at']) || '-'}</Text>
                            {form.getFieldValue(['codex_connections', field.name, 'last_error']) ? (
                              <Text type="danger">最近错误：{form.getFieldValue(['codex_connections', field.name, 'last_error'])}</Text>
                            ) : null}
                          </Space>

                          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.codex_connections?.[field.name]?.status !== cur.codex_connections?.[field.name]?.status}>
                            {({ getFieldValue }) => (
                              <div style={{ fontSize: 12, color: '#666' }}>
                                当前状态：<CodexStatusTag status={getFieldValue(['codex_connections', field.name, 'status'])} />
                              </div>
                            )}
                          </Form.Item>

                          {actionHints[connectionId] ? (
                            <Alert
                              style={{ marginTop: 12 }}
                              type="info"
                              showIcon
                              message={actionHints[connectionId].message}
                              description={(
                                <Space direction="vertical" size={6}>
                                  {actionHints[connectionId].manualCommand ? (
                                    <Text code>{actionHints[connectionId].manualCommand}</Text>
                                  ) : null}
                                  {actionHints[connectionId].details ? (
                                    <Text type="secondary">{actionHints[connectionId].details}</Text>
                                  ) : null}
                                </Space>
                              )}
                            />
                          ) : null}
                        </Card>
                      )
                    })}
                  </div>
                )}
                </Form.List>
              </>
              ),
            },
        ]}
      />
    </Form>
  )

  if (embedded) {
    return (
      <div style={{ height: '100%', overflowY: 'auto', padding: 20, background: '#fff' }}>
        <div style={{ maxWidth: 960 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#101828' }}>全局模型连接</div>
              <div style={{ fontSize: 13, color: '#667085', marginTop: 4 }}>
                在这里统一维护 API Provider 和 Codex 登录连接，所有 Workspace 共享。
              </div>
            </div>
            <Button type="primary" loading={saving} onClick={handleOk}>保存配置</Button>
          </div>
          {content}
        </div>
      </div>
    )
  }

  return (
    <Modal
      title="全局模型连接配置"
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={saving}
      width={820}
      destroyOnClose
    >
      {content}
    </Modal>
  )
}
