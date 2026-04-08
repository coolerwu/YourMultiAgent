/**
 * components/WorkerStatus.jsx
 *
 * 展示 Worker 在线状态、已注册能力与已授权能力。
 * 浏览器 Worker 支持模板授权与手动勾选。
 */

import { CheckCircleOutlined, GlobalOutlined, RobotOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Checkbox, Col, Empty, Row, Space, Table, Tag, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { workerApi } from '../utils/graphApi'

const { Text } = Typography

const BROWSER_TEMPLATES = {
  readonly: [
    'browser_open',
    'browser_get_text',
    'browser_get_title',
    'browser_exists',
    'browser_wait_for',
    'browser_screenshot',
  ],
  standard: [
    'browser_open',
    'browser_get_text',
    'browser_get_title',
    'browser_exists',
    'browser_wait_for',
    'browser_screenshot',
    'browser_click',
    'browser_type',
    'browser_press',
  ],
}

function isBrowserWorker(worker) {
  return worker.kind === 'browser'
    || worker.registered_capabilities?.some((item) => item.name.startsWith('browser_'))
}

function capabilityColor(riskLevel) {
  if (riskLevel === 'high') return 'red'
  if (riskLevel === 'medium') return 'orange'
  return 'default'
}

function formatBytes(bytes) {
  if (!bytes) return '-'
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`
  return `${bytes} B`
}

function groupCapabilities(capabilities = []) {
  const groups = {}
  capabilities.forEach((item) => {
    const key = item.category || 'general'
    if (!groups[key]) groups[key] = []
    groups[key].push(item)
  })
  return Object.entries(groups)
}

export default function WorkerStatus() {
  const [workers, setWorkers] = useState([])
  const [loading, setLoading] = useState(true)
  const [savingWorkerId, setSavingWorkerId] = useState('')

  const loadWorkers = () => {
    setLoading(true)
    workerApi.listWorkers()
      .then(setWorkers)
      .catch((e) => message.error(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadWorkers()
  }, [])

  const updateEnabledCapabilities = async (worker, capabilityNames) => {
    setSavingWorkerId(worker.worker_id)
    try {
      await workerApi.updateEnabledCapabilities(worker.worker_id, capabilityNames)
      message.success(`已更新 ${worker.label} 的授权能力`)
      loadWorkers()
    } catch (e) {
      message.error(e.message)
    } finally {
      setSavingWorkerId('')
    }
  }

  const columns = [
    {
      title: 'Capability',
      dataIndex: 'name',
      render: (name) => <Text code>{name}</Text>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      render: (value, record) => (
        <Space wrap>
          <span>{value}</span>
          {record.requires_session ? <Tag color="blue">session</Tag> : null}
          <Tag color={capabilityColor(record.risk_level)}>{record.risk_level || 'low'}</Tag>
        </Space>
      ),
    },
    {
      title: '参数',
      dataIndex: 'parameters',
      render: (params) =>
        params.map((p) => (
          <Tag key={p.name} color={p.required ? 'volcano' : 'default'}>
            {p.name}: {p.type}
          </Tag>
        )),
    },
  ]

  if (!loading && workers.length === 0) {
    return (
      <Card title="Worker 状态" size="small">
        <Empty description="暂无在线 Worker" />
      </Card>
    )
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="Worker 连接后会自动上报其真实能力；这里管理的是平台授权给它的可用能力。"
      />
      <Row gutter={[16, 16]}>
        {workers.map((worker) => {
          const enabledNames = worker.enabled_capability_names || []
          const allNames = worker.registered_capabilities.map((item) => item.name)
          const browserWorker = isBrowserWorker(worker)
          const canEdit = worker.worker_id !== 'local'

          return (
            <Col xs={24} xl={12} key={worker.worker_id}>
              <Card
                title={(
                  <Space>
                    {browserWorker ? <GlobalOutlined /> : <RobotOutlined />}
                    <span>{worker.label}</span>
                  </Space>
                )}
                size="small"
                loading={loading}
                extra={<Tag icon={<CheckCircleOutlined />} color="success">{worker.status}</Tag>}
              >
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <Space wrap>
                    <Tag>{worker.kind}</Tag>
                    <Tag>{worker.worker_id}</Tag>
                    {worker.version ? <Tag>v{worker.version}</Tag> : null}
                    {worker.platform ? <Tag>{worker.platform}</Tag> : null}
                    {worker.browser_type ? <Tag>{worker.browser_type}</Tag> : null}
                    {worker.kind === 'browser' ? <Tag>{worker.headless ? 'headless' : 'headed'}</Tag> : null}
                  </Space>

                  <Text type="secondary">
                    已授权 {enabledNames.length} / 已注册 {allNames.length}
                  </Text>

                  {(worker.browser_type || worker.source || worker.allowed_origins?.length > 0) ? (
                    <Space direction="vertical" size={4} style={{ width: '100%' }}>
                      {worker.source ? <Text type="secondary">来源：{worker.source}</Text> : null}
                      {worker.connected_at ? <Text type="secondary">连接时间：{worker.connected_at}</Text> : null}
                      {worker.last_seen_at ? <Text type="secondary">最近活动：{worker.last_seen_at}</Text> : null}
                      {worker.allowed_origins?.length > 0 ? (
                        <Text type="secondary">允许域名：{worker.allowed_origins.join(', ')}</Text>
                      ) : (
                        <Text type="secondary">允许域名：未限制</Text>
                      )}
                      {worker.kind === 'browser' ? (
                        <Text type="secondary">
                          安全限制：最多 {worker.max_sessions || '-'} 个会话，截图上限 {formatBytes(worker.max_screenshot_bytes)}，文本 {worker.max_text_chars || '-'} 字，HTML {worker.max_html_chars || '-'} 字
                        </Text>
                      ) : null}
                      {worker.last_error ? <Text type="danger">最近错误：{worker.last_error}</Text> : null}
                    </Space>
                  ) : null}

                  {browserWorker && canEdit ? (
                    <Space wrap>
                      <Button
                        size="small"
                        onClick={() => updateEnabledCapabilities(worker, BROWSER_TEMPLATES.readonly.filter((item) => allNames.includes(item)))}
                        loading={savingWorkerId === worker.worker_id}
                      >
                        只读浏览
                      </Button>
                      <Button
                        size="small"
                        onClick={() => updateEnabledCapabilities(worker, BROWSER_TEMPLATES.standard.filter((item) => allNames.includes(item)))}
                        loading={savingWorkerId === worker.worker_id}
                      >
                        标准交互
                      </Button>
                      <Button
                        size="small"
                        onClick={() => updateEnabledCapabilities(worker, allNames)}
                        loading={savingWorkerId === worker.worker_id}
                      >
                        完全开放
                      </Button>
                    </Space>
                  ) : null}

                  {canEdit ? (
                    <Checkbox.Group
                      style={{ width: '100%' }}
                      value={enabledNames}
                      onChange={(next) => updateEnabledCapabilities(worker, next)}
                    >
                      <Space direction="vertical" size={8} style={{ width: '100%' }}>
                        {groupCapabilities(worker.registered_capabilities).map(([groupName, capabilities]) => (
                          <div key={groupName}>
                            <div style={{ marginBottom: 6 }}>
                              <Text strong>{groupName}</Text>
                            </div>
                            <Space wrap>
                              {capabilities.map((item) => (
                                <Checkbox key={item.name} value={item.name}>
                                  <Space size={4}>
                                    <Text code>{item.name}</Text>
                                    <Tag color={capabilityColor(item.risk_level)}>{item.risk_level || 'low'}</Tag>
                                    {item.risk_level === 'medium' || item.risk_level === 'high' ? <Tag color="red">需谨慎</Tag> : null}
                                  </Space>
                                </Checkbox>
                              ))}
                            </Space>
                          </div>
                        ))}
                      </Space>
                    </Checkbox.Group>
                  ) : (
                    <Alert type="success" showIcon message="Local Worker 能力由系统内置管理，不支持在此处禁用。" />
                  )}

                  <Table
                    dataSource={worker.registered_capabilities}
                    columns={columns}
                    rowKey="name"
                    size="small"
                    pagination={false}
                  />
                </Space>
              </Card>
            </Col>
          )
        })}
      </Row>
    </Space>
  )
}
