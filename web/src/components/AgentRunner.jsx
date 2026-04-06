/**
 * components/AgentRunner.jsx
 *
 * 运行指定 Agent 图，流式展示输出。
 * 支持多节点标识、工具调用状态提示。
 */

import { SendOutlined } from '@ant-design/icons'
import { Button, Input, Space, Tag, Typography } from 'antd'
import { useRef, useState } from 'react'
import { graphApi } from '../utils/graphApi'

const { Text } = Typography

export default function AgentRunner({ graphId }) {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([])
  const [running, setRunning] = useState(false)
  const bottomRef = useRef(null)

  const append = (msg) => {
    setMessages((prev) => [...prev, msg])
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
  }

  const run = async () => {
    if (!input.trim() || running) return
    const userMsg = input.trim()
    setInput('')
    append({ role: 'user', content: userMsg })
    setRunning(true)

    // 占位 assistant 消息，逐步追加内容
    const assistantIdx = messages.length + 1
    setMessages((prev) => [...prev, { role: 'assistant', content: '', node: '' }])

    try {
      await graphApi.run(
        graphId,
        userMsg,
        (chunk) => {
          if (chunk.type === 'text') {
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last?.role === 'assistant') {
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + chunk.content,
                  node: chunk.node || last.node,
                }
              }
              return updated
            })
          } else if (chunk.type === 'tool_start' || chunk.type === 'tool_end') {
            append({ role: 'system', content: chunk.content })
          }
        },
        () => setRunning(false),
      )
    } catch (e) {
      append({ role: 'error', content: e.message })
      setRunning(false)
    }
  }

  const msgColor = { user: '#1677ff', assistant: '#333', system: '#888', error: '#ff4d4f' }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* 消息列表 */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 16, background: '#fafafa', borderRadius: 8 }}>
        {messages.length === 0 && (
          <Text type="secondary">输入消息，开始与 Agent 对话...</Text>
        )}
        {messages.map((msg, i) => (
          <div key={i} style={{ marginBottom: 12 }}>
            <Space align="start">
              <Tag color={msg.role === 'user' ? 'blue' : msg.role === 'system' ? 'default' : 'green'}>
                {msg.role === 'user' ? '用户' : msg.role === 'system' ? '系统' : msg.node || 'Agent'}
              </Tag>
              <Text style={{ color: msgColor[msg.role] ?? '#333', whiteSpace: 'pre-wrap' }}>
                {msg.content}
              </Text>
            </Space>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* 输入区 */}
      <Space.Compact style={{ marginTop: 12, width: '100%' }}>
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={run}
          placeholder="输入消息..."
          disabled={running}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={run}
          loading={running}
          disabled={!graphId}
        >
          发送
        </Button>
      </Space.Compact>
    </div>
  )
}
