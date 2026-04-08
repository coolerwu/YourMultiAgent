import Lottie from 'lottie-react'
import { CopyOutlined, DeleteOutlined, MessageOutlined, PlusOutlined, SendOutlined } from '@ant-design/icons'
import { Button, Drawer, Empty, Input, Space, Tag, Typography, message as antdMessage } from 'antd'
import { useEffect, useMemo, useRef, useState } from 'react'
import { workspaceApi } from '../utils/workspaceApi'

const { Text, Paragraph } = Typography
const { TextArea } = Input
const LONG_TEXT_STYLE = {
  whiteSpace: 'pre-wrap',
  overflowWrap: 'anywhere',
  wordBreak: 'break-word',
  minWidth: 0,
}

const IDLE_ANIM = { v: '5.9.0', fr: 24, ip: 0, op: 48, w: 120, h: 120, assets: [], layers: [{ ty: 4, nm: 'circle', ind: 1, ip: 0, op: 48, st: 0, ks: { o: { a: 0, k: 75 }, r: { a: 0, k: 0 }, p: { a: 0, k: [60, 60, 0] }, a: { a: 0, k: [0, 0, 0] }, s: { a: 0, k: [100, 100, 100] } }, shapes: [{ ty: 'el', p: { a: 0, k: [0, 0] }, s: { a: 0, k: [70, 70] } }, { ty: 'fl', c: { a: 0, k: [0.78, 0.87, 0.97, 1] }, o: { a: 0, k: 100 } }] }] }
const WORKING_ANIM = { v: '5.9.0', fr: 24, ip: 0, op: 48, w: 120, h: 120, assets: [], layers: [{ ty: 4, nm: 'circle', ind: 1, ip: 0, op: 48, st: 0, ks: { o: { a: 0, k: 100 }, r: { a: 1, k: [{ t: 0, s: [0] }, { t: 48, s: [360] }] }, p: { a: 0, k: [60, 60, 0] }, a: { a: 0, k: [0, 0, 0] }, s: { a: 0, k: [100, 100, 100] } }, shapes: [{ ty: 'el', p: { a: 0, k: [0, 0] }, s: { a: 0, k: [70, 70] } }, { ty: 'st', c: { a: 0, k: [0.09, 0.47, 1, 1] }, o: { a: 0, k: 100 }, w: { a: 0, k: 8 }, lc: 2, lj: 1 }] }] }
const DONE_ANIM = { v: '5.9.0', fr: 24, ip: 0, op: 36, w: 120, h: 120, assets: [], layers: [{ ty: 4, nm: 'done', ind: 1, ip: 0, op: 36, st: 0, ks: { o: { a: 0, k: 100 }, r: { a: 0, k: 0 }, p: { a: 0, k: [60, 60, 0] }, a: { a: 0, k: [0, 0, 0] }, s: { a: 1, k: [{ t: 0, s: [0, 0, 100] }, { t: 18, s: [100, 100, 100] }] } }, shapes: [{ ty: 'el', p: { a: 0, k: [0, 0] }, s: { a: 0, k: [70, 70] } }, { ty: 'fl', c: { a: 0, k: [0.32, 0.77, 0.32, 1] }, o: { a: 0, k: 100 } }] }] }

function resolveAgentModel(agent, workspace) {
  const codexConnection = workspace?.codex_connections?.find((item) => item.id === agent.codex_connection_id)
  if (codexConnection) {
    return codexConnection.name
  }
  const profile = workspace?.llm_profiles?.find((item) => item.id === agent.llm_profile_id)
  if (profile) {
    return profile.model
  }
  return agent.model
}

function formatStepLabel(step) {
  if (!step) return '待机'
  const labels = {
    step: '初始化',
    decide: '决策',
    execute: '执行',
    transition: '切换',
    finalize: '收束',
  }
  return labels[step] || step
}

function AgentCard({ agent, state, workspace }) {
  const status = state?.status || 'idle'
  const step = state?.step || ''
  const animation = status === 'working' ? WORKING_ANIM : status === 'done' ? DONE_ANIM : IDLE_ANIM
  return (
    <div style={{ width: 156, borderRadius: 14, border: `2px solid ${status === 'working' ? '#1677ff' : status === 'done' ? '#52c41a' : '#d9d9d9'}`, background: status === 'working' ? '#e6f4ff' : status === 'done' ? '#f6ffed' : '#fafafa', padding: '16px 10px 12px', textAlign: 'center' }}>
      <Lottie animationData={animation} loop={status !== 'done'} autoplay style={{ width: 80, height: 80, margin: '0 auto' }} />
      <div style={{ fontWeight: 600, fontSize: 14, marginTop: 6 }}>{agent.name}</div>
      <div style={{ fontSize: 11, color: '#999' }}>{resolveAgentModel(agent, workspace)}</div>
      <div style={{ fontSize: 11, color: status === 'working' ? '#1677ff' : status === 'done' ? '#52c41a' : '#bbb' }}>
        {status === 'working' ? '执行中...' : status === 'done' ? '完成 ✓' : '待机'}
      </div>
      <div style={{ fontSize: 11, color: '#666', marginTop: 4 }} data-testid={`agent-step-${agent.id}`}>
        {status === 'working' ? `Step: ${formatStepLabel(step)}` : `Step: ${formatStepLabel(step)}`}
      </div>
    </div>
  )
}

function mapStoredMessage(msg) {
  return {
    role: msg.role === 'user' ? 'user' : msg.role === 'event' ? 'event' : 'assistant',
    content: msg.content ?? '',
    node: msg.node ?? '',
    node_name: msg.actor_name ?? msg.node ?? '',
    actor_name: msg.actor_name ?? '',
    kind: msg.kind ?? '',
    created_at: msg.created_at ?? '',
  }
}

function normalizeSession(session) {
  return {
    id: session.id,
    title: session.title || '新会话',
    updated_at: session.updated_at || '',
    created_at: session.created_at || '',
    message_count: session.message_count ?? session.messages?.length ?? 0,
    summary: session.summary || '',
    memory_items: session.memory_items || [],
    messages: session.messages || [],
  }
}

export default function WorkspaceRunView({ workspace }) {
  const isChat = workspace?.kind === 'chat'
  const [isCompact, setIsCompact] = useState(() => (typeof window !== 'undefined' ? window.innerWidth <= 900 : false))
  const [sessionDrawerOpen, setSessionDrawerOpen] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([])
  const [running, setRunning] = useState(false)
  const [states, setStates] = useState({})
  const [orchestration, setOrchestration] = useState({ coordinator: null, workers: [] })
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState('')
  const [sessionMeta, setSessionMeta] = useState({ summary: '', memory_items: [] })
  const bottomRef = useRef(null)
  const activeSessionIdRef = useRef('')
  const participants = orchestration?.workers ?? []

  useEffect(() => {
    activeSessionIdRef.current = activeSessionId
  }, [activeSessionId])

  useEffect(() => {
    if (!workspace?.id || isChat) {
      setOrchestration({
        coordinator: workspace?.coordinator ?? null,
        workers: [],
      })
      return
    }
    workspaceApi.getOrchestration(workspace.id)
      .then(setOrchestration)
      .catch(() => setOrchestration({ coordinator: null, workers: [] }))
  }, [workspace?.id, workspace?.coordinator, isChat])

  useEffect(() => {
    const next = {}
    participants.forEach((agent) => { next[agent.id] = { status: 'idle', step: '' } })
    setStates(next)
  }, [orchestration])

  useEffect(() => {
    if (!workspace?.id) {
      setSessions([])
      setMessages([])
      setActiveSessionId('')
      setSessionMeta({ summary: '', memory_items: [] })
      return
    }

    workspaceApi.listSessions(workspace.id)
      .then((data) => {
        const normalized = data.map(normalizeSession)
        setSessions(normalized)
        if (normalized[0]) {
          setActiveSessionId(normalized[0].id)
        } else {
          setActiveSessionId('')
          setMessages([])
          setSessionMeta({ summary: '', memory_items: [] })
        }
      })
      .catch(() => {
        setSessions([])
        setActiveSessionId('')
        setMessages([])
        setSessionMeta({ summary: '', memory_items: [] })
      })
  }, [workspace?.id])

  useEffect(() => {
    const handleResize = () => {
      const compact = window.innerWidth <= 900
      setIsCompact(compact)
      if (!compact) {
        setSessionDrawerOpen(false)
      }
    }
    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
    }
  }, [])

  useEffect(() => {
    if (!workspace?.id || !activeSessionId) return
    workspaceApi.getSession(workspace.id, activeSessionId)
      .then((session) => {
        const normalized = normalizeSession(session)
        setMessages(normalized.messages.map(mapStoredMessage))
        setSessionMeta({ summary: normalized.summary, memory_items: normalized.memory_items })
        setSessions((prev) => upsertSession(prev, normalized))
      })
      .catch(() => {
        setMessages([])
        setSessionMeta({ summary: '', memory_items: [] })
      })
  }, [workspace?.id, activeSessionId])

  useEffect(() => {
    setTimeout(() => {
      if (typeof bottomRef.current?.scrollIntoView === 'function') {
        bottomRef.current.scrollIntoView({ behavior: 'smooth' })
      }
    }, 50)
  }, [messages])

  const orderedParticipants = useMemo(
    () => [...participants].sort((a, b) => (a.order || 0) - (b.order || 0)),
    [participants],
  )

  const append = (msg) => {
    setMessages((prev) => [...prev, msg])
  }

  const resolveActorName = (msg) => {
    if (msg.role === 'user') return '用户'
    if (msg.role === 'error') return '错误'
    return msg.actor_name || msg.node_name || msg.node || '智能体'
  }

  const formatMessage = (msg) => `${resolveActorName(msg)}：${msg.content ?? ''}`.trim()

  const copyMessage = async (msg) => {
    try {
      await navigator.clipboard.writeText(formatMessage(msg))
      antdMessage.success('已复制当前消息')
    } catch {
      antdMessage.error('复制失败')
    }
  }

  const copyAllMessages = async () => {
    try {
      const content = messages.map(formatMessage).join('\n\n')
      await navigator.clipboard.writeText(content)
      antdMessage.success('已复制运行记录')
    } catch {
      antdMessage.error('复制失败')
    }
  }

  const createSession = async () => {
    if (!workspace?.id) return
    const session = normalizeSession(await workspaceApi.createSession(workspace.id, {}))
    setSessions((prev) => [session, ...prev.filter((item) => item.id !== session.id)])
    setActiveSessionId(session.id)
    setMessages([])
    setSessionMeta({ summary: '', memory_items: [] })
  }

  const removeSession = async (sessionId) => {
    if (!workspace?.id || !sessionId || running) return
    await workspaceApi.deleteSession(workspace.id, sessionId)
    setSessions((prev) => {
      const next = prev.filter((item) => item.id !== sessionId)
      if (activeSessionIdRef.current === sessionId) {
        const fallback = next[0]?.id || ''
        setActiveSessionId(fallback)
        if (!fallback) {
          setMessages([])
          setSessionMeta({ summary: '', memory_items: [] })
        }
      }
      return next
    })
  }

  const run = async () => {
    if (!workspace?.id || !input.trim() || running) return
    const userMessage = input.trim()
    setRunning(true)
    setInput('')
    if (!activeSessionId) {
      setMessages([{ role: 'user', content: userMessage }])
    } else {
      append({ role: 'user', content: userMessage })
    }
    try {
      await workspaceApi.run(
        workspace.id,
        { user_message: userMessage, session_id: activeSessionId },
        (chunk) => {
          switch (chunk.type) {
            case 'session_created':
              setActiveSessionId(chunk.session_id)
              setSessions((prev) => upsertSession(prev, {
                id: chunk.session_id,
                title: chunk.title,
                updated_at: new Date().toISOString(),
                message_count: messages.length + 1,
                summary: '',
                memory_items: [],
              }))
              break
            case 'session_updated':
              setSessionMeta({ summary: chunk.summary || '', memory_items: chunk.memory_items || [] })
              setSessions((prev) => upsertSession(prev, {
                id: chunk.session_id,
                title: prevSessionTitle(prev, chunk.session_id),
                updated_at: new Date().toISOString(),
                message_count: chunk.message_count,
                summary: chunk.summary || '',
                memory_items: chunk.memory_items || [],
              }))
              break
            case 'plan_created':
              append({ role: 'event', actor_name: chunk.coordinator_name, content: `${chunk.coordinator_name} 开始拆解任务` })
              break
            case 'coordinator_start':
            case 'worker_start':
              setStates((prev) => ({ ...prev, [chunk.node]: { status: 'working', step: '' } }))
              append({ role: 'event', actor_name: chunk.actor_name, content: `▶ ${chunk.node_name} 开始执行`, node: chunk.node, node_name: chunk.node_name })
              setMessages((prev) => [...prev, { role: 'assistant', content: '', node: chunk.node, node_name: chunk.node_name, actor_name: chunk.actor_name }])
              break
            case 'coordinator_end':
            case 'worker_end':
              setStates((prev) => ({ ...prev, [chunk.node]: { status: 'done', step: prev[chunk.node]?.step || '' } }))
              break
            case 'step_changed':
              setStates((prev) => ({
                ...prev,
                [chunk.node]: {
                  status: prev[chunk.node]?.status || 'working',
                  step: chunk.step || '',
                },
              }))
              append({ role: 'event', actor_name: chunk.actor_name, content: `进入步骤：${formatStepLabel(chunk.step)}`, node: chunk.node, node_name: chunk.node_name, kind: 'step_changed' })
              break
            case 'task_assigned':
              append({ role: 'event', actor_name: chunk.actor_name, content: `已分派给 ${chunk.worker_name}：${chunk.assignment}` })
              break
            case 'worker_result':
              append({ role: 'event', actor_name: chunk.actor_name, content: `${chunk.worker_name} 已交付结果` })
              break
            case 'run_summary':
              append({ role: 'event', actor_name: chunk.actor_name, content: chunk.summary })
              break
            case 'text':
              setMessages((prev) => {
                const updated = [...prev]
                for (let index = updated.length - 1; index >= 0; index -= 1) {
                  if (updated[index].role === 'assistant' && updated[index].node === chunk.node) {
                    updated[index] = { ...updated[index], content: updated[index].content + chunk.content, actor_name: chunk.actor_name }
                    return updated
                  }
                }
                return updated
              })
              break
            case 'tool_start':
              append({ role: 'event', actor_name: chunk.actor_name, content: `🔧 ${chunk.tool}` })
              break
            case 'tool_end':
              append({ role: 'event', actor_name: chunk.actor_name, content: `└ ${String(chunk.result).slice(0, 180)}` })
              break
            default:
              break
          }
        },
        async () => {
          setRunning(false)
          if (workspace?.id && activeSessionIdRef.current) {
            try {
              const session = normalizeSession(await workspaceApi.getSession(workspace.id, activeSessionIdRef.current))
              setMessages(session.messages.map(mapStoredMessage))
              setSessionMeta({ summary: session.summary, memory_items: session.memory_items })
              setSessions((prev) => upsertSession(prev, session))
            } catch (_) {
              // ignore
            }
          }
        },
        (e) => {
          append({ role: 'error', content: e.message })
          setRunning(false)
        },
      )
    } catch (e) {
      append({ role: 'error', content: e.message })
      setRunning(false)
    }
  }

  if (!workspace) {
    return <div style={{ padding: 32, color: '#aaa', fontSize: 14 }}>请先选择一个 Workspace</div>
  }

  const renderSessionList = () => (
    <div style={{ width: 280, borderRight: isCompact ? 'none' : '1px solid #f0f0f0', background: '#fafafa', display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: 12, borderBottom: '1px solid #f0f0f0' }}>
        <Button type="primary" icon={<PlusOutlined />} block onClick={createSession} disabled={running}>
          新建会话
        </Button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: 10 }}>
        {sessions.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无历史会话" />}
        {sessions.map((session) => (
          <div
            key={session.id}
            onClick={() => {
              setActiveSessionId(session.id)
              setSessionDrawerOpen(false)
            }}
            style={{
              padding: 12,
              borderRadius: 12,
              cursor: 'pointer',
              background: session.id === activeSessionId ? '#e6f4ff' : '#fff',
              border: session.id === activeSessionId ? '1px solid #91caff' : '1px solid #f0f0f0',
              marginBottom: 8,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <Text strong ellipsis style={{ maxWidth: 180 }}>{session.title || '新会话'}</Text>
              <Button
                size="small"
                type="text"
                icon={<DeleteOutlined />}
                onClick={(event) => {
                  event.stopPropagation()
                  removeSession(session.id).catch(() => antdMessage.error('删除会话失败'))
                }}
                disabled={running}
              />
            </div>
            <div style={{ marginTop: 6 }}>
              <Tag icon={<MessageOutlined />} color="default">{session.message_count || 0} 条</Tag>
            </div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {formatTime(session.updated_at)}
            </Text>
          </div>
        ))}
      </div>
    </div>
  )

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      {!isCompact && renderSessionList()}

      <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
        {isChat ? (
          <div style={{ padding: '16px', background: '#f7f8fa', borderBottom: '1px solid #f0f0f0' }}>
            {isCompact && (
              <div style={{ marginBottom: 10 }}>
                <Button icon={<MessageOutlined />} onClick={() => setSessionDrawerOpen(true)}>
                  会话列表
                </Button>
              </div>
            )}
            <Text strong>{workspace?.name || '单聊目录'}</Text>
            <div style={{ marginTop: 6 }}>
              <Text type="secondary">当前目录中的历史会话、compact 摘要和 memory 会持续复用。</Text>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 20, padding: '20px 16px', background: '#f7f8fa', borderBottom: '1px solid #f0f0f0', minHeight: 190 }}>
            {isCompact && (
              <div style={{ width: '100%' }}>
                <Button icon={<MessageOutlined />} onClick={() => setSessionDrawerOpen(true)}>
                  会话列表
                </Button>
              </div>
            )}
            {orderedParticipants.map((agent) => <AgentCard key={agent.id} agent={agent} state={states[agent.id] || 'idle'} workspace={workspace} />)}
          </div>
        )}
        <div style={{ padding: '10px 16px', background: '#fcfcfc', borderBottom: '1px solid #f0f0f0' }}>
          {sessionMeta.summary
            ? (
              <Paragraph
                data-testid="session-summary"
                style={{ marginBottom: 8, ...LONG_TEXT_STYLE }}
                ellipsis={{ rows: 2, expandable: true, symbol: '展开摘要' }}
              >
                <Text strong>Compact 摘要：</Text> {sessionMeta.summary}
              </Paragraph>
            )
            : <Text type="secondary">当前会话尚未触发 compact。</Text>}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
            {sessionMeta.memory_items?.map((item) => (
              <Tag
                key={item.id}
                data-testid={`memory-item-${item.id}`}
                color="processing"
                style={{ maxWidth: '100%', height: 'auto', ...LONG_TEXT_STYLE }}
              >
                {item.category}: {item.content}
              </Tag>
            ))}
          </div>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px', background: '#fff' }}>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
            <Button icon={<CopyOutlined />} onClick={copyAllMessages} disabled={messages.length === 0}>复制运行记录</Button>
          </div>
          {messages.length === 0 && <Text type="secondary">{isChat ? '输入消息后，当前单聊目录会继续沿用已有记忆和历史上下文。' : '输入任务，主控智能体会拆解并分派给各 Worker。'}</Text>}
          {messages.map((msg, index) => (
            <div key={`${msg.created_at || index}-${index}`} style={{ marginBottom: 8, display: 'flex', alignItems: 'flex-start', gap: 8, width: '100%' }}>
              <Tag color={msg.role === 'user' ? 'blue' : msg.role === 'error' ? 'red' : msg.role === 'assistant' ? 'green' : 'default'}>
                {msg.role === 'user' ? '用户' : msg.role === 'error' ? '错误' : resolveActorName(msg)}
              </Tag>
              <Text data-testid={`message-content-${index}`} style={{ flex: 1, ...LONG_TEXT_STYLE }}>{msg.content}</Text>
              <Button size="small" type="text" icon={<CopyOutlined />} onClick={() => copyMessage(msg)} />
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
        <div style={{ padding: '12px 16px', borderTop: '1px solid #f0f0f0' }}>
          <Space.Compact style={{ width: '100%' }}>
            <TextArea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                  e.preventDefault()
                  run()
                }
              }}
              disabled={running}
              autoSize={{ minRows: 2, maxRows: 6 }}
              placeholder={isChat ? '输入消息...（Ctrl+Enter 发送）' : '输入任务，交给主控智能体...（Ctrl+Enter 发送）'}
            />
            <Button type="primary" icon={<SendOutlined />} onClick={run} loading={running}>发送</Button>
          </Space.Compact>
        </div>
      </div>
      <Drawer
        title="会话列表"
        placement="left"
        width={300}
        open={isCompact && sessionDrawerOpen}
        onClose={() => setSessionDrawerOpen(false)}
        styles={{ body: { padding: 0 } }}
      >
        {renderSessionList()}
      </Drawer>
    </div>
  )
}

function upsertSession(list, session) {
  const next = [normalizeSession(session), ...list.filter((item) => item.id !== session.id)]
  next.sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''))
  return next
}

function prevSessionTitle(sessions, sessionId) {
  return sessions.find((item) => item.id === sessionId)?.title || '新会话'
}

function formatTime(value) {
  if (!value) return '刚刚'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}
