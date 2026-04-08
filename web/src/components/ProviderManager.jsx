/**
 * components/ProviderManager.jsx
 *
 * Provider 配置弹窗：维护全局共享的 API Provider 与 Codex 登录连接。
 */

import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { Button, Card, Form, Input, Modal, Select, Space, Tabs, Tag, message } from 'antd'
import { useEffect, useState } from 'react'
import { workspaceApi } from '../utils/workspaceApi'

const { Option } = Select

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

  useEffect(() => {
    if (!embedded && !open) return
    workspaceApi.getProviderSettings()
      .then((settings) => {
        form.setFieldsValue({
          default_provider: settings.default_provider ?? 'anthropic',
          default_model: settings.default_model ?? 'claude-sonnet-4-6',
          default_base_url: settings.default_base_url ?? '',
          default_api_key: settings.default_api_key ?? '',
          llm_profiles: settings.llm_profiles ?? [],
          codex_connections: settings.codex_connections ?? [],
        })
      })
      .catch((e) => message.error(e.message))
  }, [open, form])

  const handleOk = async () => {
    let vals
    try {
      vals = await form.validateFields()
    } catch {
      return
    }

    const payload = {
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

    setSaving(true)
    try {
      const saved = await workspaceApi.updateProviderSettings(payload)
      message.success('全局模型连接配置已更新')
      onSaved?.(saved)
      onClose?.()
    } catch (e) {
      message.error(e.message)
    } finally {
      setSaving(false)
    }
  }

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
                          id: '',
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

                    {fields.map((field) => (
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
                          <Form.Item
                            name={[field.name, 'account_label']}
                            label="账号标识"
                            style={{ flex: 1 }}
                          >
                            <Input placeholder="例如：you@example.com" />
                          </Form.Item>
                          <Form.Item
                            name={[field.name, 'status']}
                            label="连接状态"
                            style={{ width: 160 }}
                          >
                            <Select>
                              <Option value="disconnected">未连接</Option>
                              <Option value="connected">已连接</Option>
                              <Option value="expired">已过期</Option>
                            </Select>
                          </Form.Item>
                        </Space>

                        <Space size={12} style={{ width: '100%' }} align="start">
                          <Form.Item name={[field.name, 'credential_ref']} label="凭据引用" style={{ flex: 1 }}>
                            <Input placeholder="例如：~/.codex/auth.json" />
                          </Form.Item>
                          <Form.Item name={[field.name, 'last_verified_at']} label="最近校验时间" style={{ flex: 1 }}>
                            <Input placeholder="例如：2026-04-08T10:30:00+08:00" />
                          </Form.Item>
                        </Space>

                        <Form.Item noStyle shouldUpdate={(prev, cur) => prev.codex_connections?.[field.name]?.status !== cur.codex_connections?.[field.name]?.status}>
                          {({ getFieldValue }) => (
                            <div style={{ fontSize: 12, color: '#666' }}>
                              当前状态：<CodexStatusTag status={getFieldValue(['codex_connections', field.name, 'status'])} />
                            </div>
                          )}
                        </Form.Item>
                      </Card>
                    ))}
                  </div>
                )}
              </Form.List>
            ),
          },
        ]}
      />
    </Form>
  )

  if (embedded) {
    return (
      <div style={{ padding: 20, background: '#fff', minHeight: '100vh' }}>
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
