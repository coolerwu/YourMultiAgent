import { FileTextOutlined, ReloadOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Input, Select, Space, Switch, Typography, message } from 'antd'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { workspaceApi } from '../utils/workspaceApi'

const { Text } = Typography
const APP_LOG_LINES = 300
const REFRESH_INTERVAL_OPTIONS = [
  { value: 3, label: '3 秒' },
  { value: 5, label: '5 秒' },
  { value: 10, label: '10 秒' },
  { value: 30, label: '30 秒' },
]

export default function AppLogViewer() {
  const [appLog, setAppLog] = useState({
    filename: 'app.log',
    path: '',
    content: '',
    line_count: 0,
    exists: false,
  })
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshIntervalSec, setRefreshIntervalSec] = useState(5)
  const logContainerRef = useRef(null)
  const keepAtBottomRef = useRef(true)

  const loadAppLog = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true)
    try {
      const result = await workspaceApi.getAppLog(APP_LOG_LINES)
      setAppLog(result)
    } catch (e) {
      if (!silent) message.error(e.message)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAppLog()
  }, [loadAppLog])

  useEffect(() => {
    if (!autoRefresh) return undefined
    const timer = window.setInterval(() => {
      loadAppLog({ silent: true })
    }, refreshIntervalSec * 1000)
    return () => window.clearInterval(timer)
  }, [autoRefresh, refreshIntervalSec, loadAppLog])

  const visibleContent = useMemo(() => {
    const raw = appLog.content || ''
    if (!keyword.trim()) return raw
    const matcher = keyword.trim().toLowerCase()
    return raw
      .split('\n')
      .filter((line) => line.toLowerCase().includes(matcher))
      .join('\n')
  }, [appLog.content, keyword])

  useEffect(() => {
    const container = logContainerRef.current
    if (!container || !keepAtBottomRef.current) return
    container.scrollTop = container.scrollHeight
  }, [visibleContent, appLog.exists])

  const handleLogScroll = () => {
    const container = logContainerRef.current
    if (!container) return
    const threshold = 24
    const distance = container.scrollHeight - container.scrollTop - container.clientHeight
    keepAtBottomRef.current = distance <= threshold
  }

  return (
    <div
      data-testid="app-log-scroll"
      style={{ height: '100%', overflowY: 'auto', padding: 20, background: '#fff' }}
    >
      <div style={{ maxWidth: 960 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#101828' }}>应用日志</div>
            <div style={{ fontSize: 13, color: '#667085', marginTop: 4 }}>
              查看当前宿主机唯一的 app.log，默认展示最近 300 行。
            </div>
          </div>
        </div>

        <Card style={{ marginBottom: 12 }}>
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <Text type="secondary">
              当前只保留一个应用日志文件：{appLog.filename || 'app.log'}
              {appLog.path ? `（${appLog.path}）` : ''}
            </Text>
            <Text type="secondary">
              展示最近 {APP_LOG_LINES} 行，当前文件总行数：{appLog.line_count ?? 0}
            </Text>
            <Space wrap size={12}>
              <Input.Search
                data-testid="app-log-search"
                allowClear
                placeholder="搜索日志关键字（区分大小写关闭）"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                style={{ width: 360 }}
              />
              <Space size={6}>
                <Text type="secondary">定时刷新</Text>
                <Switch checked={autoRefresh} onChange={setAutoRefresh} />
              </Space>
              <Select
                value={refreshIntervalSec}
                onChange={setRefreshIntervalSec}
                disabled={!autoRefresh}
                options={REFRESH_INTERVAL_OPTIONS}
                style={{ width: 110 }}
              />
              <Button
                size="small"
                icon={<ReloadOutlined />}
                loading={loading}
                onClick={() => loadAppLog()}
              >
                刷新日志
              </Button>
            </Space>
          </Space>
        </Card>

        <Card
          title={(
            <Space size={8}>
              <FileTextOutlined />
              <span>app.log（日志内容）</span>
            </Space>
          )}
        >
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
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
                ref={logContainerRef}
                onScroll={handleLogScroll}
                style={{
                  margin: 0,
                  padding: 12,
                  minHeight: 360,
                  maxHeight: '70vh',
                  overflow: 'auto',
                  background: '#0f172a',
                  color: '#e2e8f0',
                  borderRadius: 8,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {visibleContent || '没有匹配的日志内容'}
              </pre>
            )}
          </Space>
        </Card>
      </div>
    </div>
  )
}
