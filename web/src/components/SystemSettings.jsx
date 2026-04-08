import { ReloadOutlined, SettingOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Popconfirm, Space, Typography, message } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { workspaceApi } from '../utils/workspaceApi'

const { Text } = Typography

export default function SystemSettings() {
  const [updateStatus, setUpdateStatus] = useState({
    status: 'idle',
    logs: [],
    steps: [],
    error: '',
  })

  useEffect(() => {
    workspaceApi.getUpdateNowStatus().then(setUpdateStatus).catch((e) => message.error(e.message))
  }, [])

  useEffect(() => {
    if (!['running', 'restarting'].includes(updateStatus.status)) return
    const timer = window.setInterval(() => {
      workspaceApi.getUpdateNowStatus().then(setUpdateStatus).catch(() => {})
    }, 1500)
    return () => window.clearInterval(timer)
  }, [updateStatus.status])

  const handleUpdateNow = async () => {
    try {
      const result = await workspaceApi.startUpdateNow()
      setUpdateStatus(result)
      message.success(result.status === 'running' ? '已开始执行增量更新' : '更新任务已在运行中')
    } catch (e) {
      message.error(e.message)
    }
  }

  const updateStatusTone = useMemo(() => {
    if (updateStatus.status === 'failed') return 'error'
    if (updateStatus.status === 'success') return 'success'
    if (updateStatus.status === 'running' || updateStatus.status === 'restarting') return 'info'
    return 'info'
  }, [updateStatus.status])

  const updateStatusMessage = useMemo(() => {
    if (updateStatus.status === 'failed') return 'Update Now 执行失败'
    if (updateStatus.status === 'success') return 'Update Now 已完成'
    if (updateStatus.status === 'running') return 'Update Now 执行中'
    if (updateStatus.status === 'restarting') return 'Update Now 正在重启服务'
    return '点击按钮后执行 git pull、依赖同步并重启当前服务'
  }, [updateStatus.status])

  return (
    <div style={{ padding: 20, background: '#fff', minHeight: '100vh' }}>
      <div style={{ maxWidth: 960 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#101828' }}>系统设置</div>
            <div style={{ fontSize: 13, color: '#667085', marginTop: 4 }}>
              管理当前服务的增量更新和系统级操作。
            </div>
          </div>
        </div>

        <Card
          title={(
            <Space size={8}>
              <SettingOutlined />
              <span>Update Now</span>
            </Space>
          )}
          extra={(
            <Popconfirm
              title="执行 Update Now"
              description="将执行增量更新、同步依赖并重启当前服务。"
              okText="开始更新"
              cancelText="取消"
              onConfirm={handleUpdateNow}
              disabled={updateStatus.status === 'running' || updateStatus.status === 'restarting'}
            >
              <Button
                icon={<ReloadOutlined />}
                loading={updateStatus.status === 'running' || updateStatus.status === 'restarting'}
              >
                Update Now
              </Button>
            </Popconfirm>
          )}
        >
          <Alert
            type={updateStatusTone}
            showIcon
            message={updateStatusMessage}
            description={(
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Text type="secondary">
                  当前状态：{updateStatus.status}
                  {updateStatus.target_commit_before ? `；更新前：${updateStatus.target_commit_before.slice(0, 8)}` : ''}
                  {updateStatus.target_commit_after ? `；更新后：${updateStatus.target_commit_after.slice(0, 8)}` : ''}
                </Text>
                {updateStatus.steps?.length ? (
                  <Text type="secondary">
                    {updateStatus.steps.map((step) => `${step.name}:${step.status}`).join(' / ')}
                  </Text>
                ) : null}
                {updateStatus.error ? <Text type="danger">{updateStatus.error}</Text> : null}
                {updateStatus.logs?.length ? (
                  <pre
                    style={{
                      margin: 0,
                      padding: 12,
                      maxHeight: 280,
                      overflow: 'auto',
                      background: '#0f172a',
                      color: '#e2e8f0',
                      borderRadius: 8,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {updateStatus.logs.join('\n\n')}
                  </pre>
                ) : null}
              </Space>
            )}
          />
        </Card>
      </div>
    </div>
  )
}
