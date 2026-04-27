import { LockOutlined, LoginOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Form, Input, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { authApi, getAuthToken, setAuthToken } from '../utils/api'

const { Text } = Typography

export default function LoginGate({ children }) {
  const [checking, setChecking] = useState(true)
  const [authEnabled, setAuthEnabled] = useState(false)
  const [authenticated, setAuthenticated] = useState(Boolean(getAuthToken()))
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    authApi.status()
      .then((status) => {
        setAuthEnabled(Boolean(status.enabled))
        setAuthenticated(!status.enabled || Boolean(getAuthToken()))
      })
      .catch((e) => message.error(e.message))
      .finally(() => setChecking(false))
  }, [])

  const handleLogin = async (values) => {
    setSubmitting(true)
    try {
      const result = await authApi.login({
        access_key: String(values.access_key || '').trim(),
        secret_key: String(values.secret_key || ''),
      })
      setAuthToken(result.token)
      setAuthenticated(true)
      message.success('登录成功')
    } catch (e) {
      message.error('登录失败，请检查 Access Key / Secret Key')
    } finally {
      setSubmitting(false)
    }
  }

  if (checking) {
    return <div style={{ minHeight: '100vh', background: '#fff' }} />
  }

  if (!authEnabled || authenticated) {
    return children
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        background: '#f6f8fb',
        padding: 24,
      }}
    >
      <Card
        style={{ width: '100%', maxWidth: 380, borderRadius: 8 }}
        title={(
          <span>
            <LockOutlined style={{ marginRight: 8 }} />
            登录 YourMultiAgent
          </span>
        )}
      >
        <Form layout="vertical" onFinish={handleLogin}>
          <Form.Item
            name="access_key"
            label="Access Key"
            rules={[{ required: true, message: '请输入 Access Key' }]}
          >
            <Input autoFocus autoComplete="username" />
          </Form.Item>
          <Form.Item
            name="secret_key"
            label="Secret Key"
            rules={[{ required: true, message: '请输入 Secret Key' }]}
          >
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block icon={<LoginOutlined />} loading={submitting}>
            登录
          </Button>
        </Form>
        <Alert
          type="info"
          showIcon
          style={{ marginTop: 16 }}
          message={<Text type="secondary">此登录仅用于保护当前 Web 页面和后端接口。</Text>}
        />
      </Card>
    </div>
  )
}
