import { FileTextOutlined, ReloadOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Space, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { workspaceApi } from '../utils/workspaceApi'

const { Text } = Typography
const APP_LOG_LINES = 300

export default function AppLogViewer() {
  const [appLog, setAppLog] = useState({
    filename: 'app.log',
    path: '',
    content: '',
    line_count: 0,
    exists: false,
  })
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadAppLog()
    const timer = window.setInterval(() => {
      loadAppLog({ silent: true })
    }, 5000)
    return () => window.clearInterval(timer)
  }, [])

  const loadAppLog = async ({ silent = false } = {}) => {
    if (!silent) setLoading(true)
    try {
      const result = await workspaceApi.getAppLog(APP_LOG_LINES)
      setAppLog(result)
    } catch (e) {
      if (!silent) message.error(e.message)
    } finally {
      if (!silent) setLoading(false)
    }
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

        <Card
          title={(
            <Space size={8}>
              <FileTextOutlined />
              <span>app.log</span>
            </Space>
          )}
          extra={(
            <Button
              size="small"
              icon={<ReloadOutlined />}
              loading={loading}
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
