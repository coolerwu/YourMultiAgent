/**
 * components/ProviderManager.jsx
 *
 * Provider 配置弹窗：按 Workspace 维护可复用的 LLM / Provider 配置。
 */

import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { Button, Card, Form, Input, Modal, Select, Space, message } from 'antd'
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

export default function ProviderManager({ open, workspace, onClose, onSaved }) {
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open || !workspace) return
    form.setFieldsValue({
      llm_profiles: workspace.llm_profiles ?? [],
    })
  }, [open, workspace, form])

  const handleOk = async () => {
    if (!workspace) return
    let vals
    try {
      vals = await form.validateFields()
    } catch {
      return
    }

    const payload = {
      ...workspace,
      llm_profiles: (vals.llm_profiles ?? []).map((profile, index) => ({
        ...profile,
        id: profile.id || `llm_${Date.now()}_${index}`,
      })),
    }

    setSaving(true)
    try {
      const saved = await workspaceApi.update(workspace.id, payload)
      message.success('Provider 配置已更新')
      onSaved?.(saved)
      onClose?.()
    } catch (e) {
      message.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title={workspace ? `${workspace.name} / Provider 配置` : 'Provider 配置'}
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={saving}
      width={760}
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.List name="llm_profiles">
          {(fields, { add, remove }) => (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div>
                  <div style={{ fontWeight: 600 }}>可复用 Provider</div>
                  <div style={{ fontSize: 12, color: '#888' }}>
                    在这里统一维护接口、模型和 Token，节点直接引用
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
      </Form>
    </Modal>
  )
}
