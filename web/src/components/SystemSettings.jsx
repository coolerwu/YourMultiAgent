import { FileTextOutlined, LoginOutlined, ReloadOutlined, SettingOutlined, SyncOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Popconfirm, Space, Typography, message } from 'antd'
import { useEffect, useMemo, useRef, useState } from 'react'
import { workspaceApi } from '../utils/workspaceApi'

const { Text } = Typography
const APP_LOG_LINES = 300

export default function SystemSettings() {
  const hasTriggeredReloadRef = useRef(false)
  const shouldReloadOnSuccessRef = useRef(false)
  const [codexConnections, setCodexConnections] = useState([])
  const [codexActionHints, setCodexActionHints] = useState({})
  const [runningCodexActionId, setRunningCodexActionId] = useState('')
  const [appLog, setAppLog] = useState({
    filename: 'app.log',
    path: '',
    content: '',
    line_count: 0,
    exists: false,
  })
  const [appLogLoading, setAppLogLoading] = useState(false)
  const [updateStatus, setUpdateStatus] = useState({
    status: 'idle',
    logs: [],
    steps: [],
    error: '',
  })

  useEffect(() => {
    loadData()
  }, [])

  useEffect(() => {
    const timer = window.setInterval(() => {
      loadAppLog({ silent: true })
    }, 5000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!['running', 'restarting'].includes(updateStatus.status)) return
    shouldReloadOnSuccessRef.current = true
    const timer = window.setInterval(() => {
      workspaceApi.getUpdateNowStatus().then(setUpdateStatus).catch(() => {})
    }, 1500)
    return () => window.clearInterval(timer)
  }, [updateStatus.status])

  useEffect(() => {
    if (updateStatus.status !== 'success' || hasTriggeredReloadRef.current || !shouldReloadOnSuccessRef.current) return
    hasTriggeredReloadRef.current = true
    message.success('Update Now 已完成，正在刷新页面')
    const timer = window.setTimeout(() => {
      window.location.reload()
    }, 800)
    return () => window.clearTimeout(timer)
  }, [updateStatus.status])

  const loadData = async () => {
    try {
      const [status, settings, logResult] = await Promise.all([
        workspaceApi.getUpdateNowStatus(),
        workspaceApi.getProviderSettings(),
        workspaceApi.getAppLog(APP_LOG_LINES),
      ])
      setUpdateStatus(status)
      setCodexConnections(settings.codex_connections ?? [])
      setAppLog(logResult)
    } catch (e) {
      message.error(e.message)
    }
  }

  const loadAppLog = async ({ silent = false } = {}) => {
    if (!silent) setAppLogLoading(true)
    try {
      const result = await workspaceApi.getAppLog(APP_LOG_LINES)
      setAppLog(result)
    } catch (e) {
      if (!silent) message.error(e.message)
    } finally {
      if (!silent) setAppLogLoading(false)
    }
  }

  const handleUpdateNow = async () => {
    try {
      const result = await workspaceApi.startUpdateNow()
      setUpdateStatus(result)
      message.success(result.status === 'running' ? '已开始执行增量更新' : '更新任务已在运行中')
    } catch (e) {
      message.error(e.message)
    }
  }

  const handleCodexAction = async (connectionId, action) => {
    setRunningCodexActionId(`${action}:${connectionId}`)
    try {
      const result = action === 'check'
        ? await workspaceApi.checkCodexConnection(connectionId)
        : action === 'install'
          ? await workspaceApi.installCodexConnection(connectionId)
          : await workspaceApi.loginCodexConnection(connectionId)
      setCodexActionHints((prev) => ({
        ...prev,
        [connectionId]: {
          message: result.message,
          manualCommand: result.manual_command ?? '',
          details: result.details ?? '',
        },
      }))
      message.success(result.message)
      await loadData()
    } catch (e) {
      message.error(e.message)
    } finally {
      setRunningCodexActionId('')
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
    <div
      data-testid="system-settings-scroll"
      style={{ height: '100%', overflowY: 'auto', padding: 20, background: '#fff' }}
    >
      <div style={{ maxWidth: 960 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#101828' }}>系统设置</div>
            <div style={{ fontSize: 13, color: '#667085', marginTop: 4 }}>
              管理当前服务的增量更新，以及宿主机上的 Codex 运行时。
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

        <div style={{ height: 16 }} />

        <Card
          title={(
            <Space size={8}>
              <SyncOutlined />
              <span>Codex 运行时</span>
            </Space>
          )}
        >
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Alert
              type="info"
              showIcon
              message="管理宿主机上的 Codex CLI"
              description="更新 Codex 只影响当前机器上的 codex CLI，不会更新应用服务本身。当前同一台宿主机只维护一份 Codex 安装和一份登录态，不支持在这里并行登录多个不同账号。安装或更新完成后，请退出终端并重新进入，再执行 codex login --device-auth。"
            />

            {codexConnections.length === 0 ? (
              <Alert
                type="warning"
                showIcon
                message="当前还没有配置 Codex 连接"
                description="请先到“全局模型连接”里新增至少一个 Codex 连接，然后再回到这里执行更新和登录。"
              />
            ) : null}

            {codexConnections.map((connection) => (
              <Card
                key={connection.id}
                size="small"
                title={connection.name || '未命名 Codex 连接'}
                extra={<Text type="secondary">{connection.status || 'disconnected'}</Text>}
              >
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Text type="secondary">安装状态：{connection.install_status || 'unknown'}</Text>
                  <Text type="secondary">登录状态：{connection.login_status || 'unknown'}</Text>
                  <Text type="secondary">CLI 版本：{connection.cli_version || '-'}</Text>
                  <Text type="secondary">安装路径：{connection.install_path || '-'}</Text>
                  <Text type="secondary">最近错误：{connection.last_error || '-'}</Text>

                  <Space wrap>
                    <Button
                      size="small"
                      loading={runningCodexActionId === `check:${connection.id}`}
                      onClick={() => handleCodexAction(connection.id, 'check')}
                    >
                      检测环境
                    </Button>
                    <Button
                      size="small"
                      icon={<ReloadOutlined />}
                      loading={runningCodexActionId === `install:${connection.id}`}
                      onClick={() => handleCodexAction(connection.id, 'install')}
                    >
                      {connection.install_status === 'installed' ? '更新 Codex' : '安装 Codex'}
                    </Button>
                    <Button
                      size="small"
                      icon={<LoginOutlined />}
                      loading={runningCodexActionId === `login:${connection.id}`}
                      onClick={() => handleCodexAction(connection.id, 'login')}
                    >
                      登录 Codex
                    </Button>
                  </Space>

                  {codexActionHints[connection.id] ? (
                    <Alert
                      type="info"
                      showIcon
                      message={codexActionHints[connection.id].message}
                      description={(
                        <Space direction="vertical" size={6}>
                          {codexActionHints[connection.id].manualCommand ? (
                            <Text code>{codexActionHints[connection.id].manualCommand}</Text>
                          ) : null}
                          {codexActionHints[connection.id].details ? (
                            <Text type="secondary">{codexActionHints[connection.id].details}</Text>
                          ) : null}
                        </Space>
                      )}
                    />
                  ) : null}
                </Space>
              </Card>
            ))}
          </Space>
        </Card>

        <div style={{ height: 16 }} />

        <Card
          title={(
            <Space size={8}>
              <FileTextOutlined />
              <span>应用日志</span>
            </Space>
          )}
          extra={(
            <Button
              size="small"
              icon={<ReloadOutlined />}
              loading={appLogLoading}
              onClick={() => loadAppLog()}
            >
              刷新日志
            </Button>
          )}
        >
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <Text type="secondary">
              当前只保留一个应用日志文件：{appLog.filename || 'app.log'}
              {appLog.path ? `（${appLog.path}）` : ''}
            </Text>
            <Text type="secondary">
              展示最近 {APP_LOG_LINES} 行，当前文件总行数：{appLog.line_count ?? 0}
            </Text>
            {!appLog.exists ? (
              <Alert
                type="info"
                showIcon
                message="app.log 尚未生成"
                description="当服务启动并产生日志后，这里会直接展示统一应用日志。"
              />
            ) : (
              <pre
                data-testid="system-app-log"
                style={{
                  margin: 0,
                  padding: 12,
                  minHeight: 220,
                  maxHeight: 420,
                  overflow: 'auto',
                  background: '#0f172a',
                  color: '#e2e8f0',
                  borderRadius: 8,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {appLog.content || 'app.log 当前为空'}
              </pre>
            )}
          </Space>
        </Card>
      </div>
    </div>
  )
}
