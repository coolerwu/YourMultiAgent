/**
 * components/AgentRunView.jsx
 *
 * Agent 运行视图：以"员工卡片"形式展示各 Agent 协作过程。
 *
 * - 每个 Agent 是一张卡片，带 Lottie 动画（idle / working / done）
 * - SSE 事件驱动：node_start→工作动画，node_end→完成动画
 * - 文件传递动画：收到 edge 事件后，文件徽章飞向下一个 Agent
 * - 消息流：对话历史 + 工具调用记录
 *
 * Lottie 动画数据内联（无需外部文件）：
 *   idle    — 轻微呼吸脉冲（灰蓝圆圈）
 *   working — 旋转弧（蓝色 spinner）
 *   done    — 弹入绿圆
 */

import Lottie from 'lottie-react'
import { SendOutlined } from '@ant-design/icons'
import { Button, Input, Space, Tag, Typography } from 'antd'
import { useCallback, useEffect, useRef, useState } from 'react'
import { graphApi } from '../utils/graphApi'

const { Text } = Typography

// ── Lottie 动画数据 ────────────────────────────────────────────

const IDLE_ANIM = {
  v: '5.9.0', fr: 24, ip: 0, op: 48, w: 120, h: 120,
  assets: [],
  layers: [{
    ty: 4, nm: 'circle', ind: 1, ip: 0, op: 48, st: 0,
    ks: {
      o: { a: 1, k: [
        { t: 0, s: [35], i: { x: [0.5], y: [1] }, o: { x: [0.5], y: [0] } },
        { t: 24, s: [90], i: { x: [0.5], y: [1] }, o: { x: [0.5], y: [0] } },
        { t: 48, s: [35] },
      ] },
      r: { a: 0, k: 0 },
      p: { a: 0, k: [60, 60, 0] },
      a: { a: 0, k: [0, 0, 0] },
      s: { a: 0, k: [100, 100, 100] },
    },
    shapes: [
      { ty: 'el', p: { a: 0, k: [0, 0] }, s: { a: 0, k: [68, 68] } },
      { ty: 'fl', c: { a: 0, k: [0.78, 0.87, 0.97, 1] }, o: { a: 0, k: 100 } },
    ],
  }],
}

const WORKING_ANIM = {
  v: '5.9.0', fr: 30, ip: 0, op: 60, w: 120, h: 120,
  assets: [],
  layers: [
    // 灰色底圆轨道
    {
      ty: 4, nm: 'track', ind: 2, ip: 0, op: 60, st: 0,
      ks: {
        o: { a: 0, k: 100 }, r: { a: 0, k: 0 },
        p: { a: 0, k: [60, 60, 0] }, a: { a: 0, k: [0, 0, 0] }, s: { a: 0, k: [100, 100, 100] },
      },
      shapes: [
        { ty: 'el', p: { a: 0, k: [0, 0] }, s: { a: 0, k: [80, 80] } },
        { ty: 'st', c: { a: 0, k: [0.9, 0.9, 0.9, 1] }, o: { a: 0, k: 100 }, w: { a: 0, k: 8 }, lc: 2, lj: 1 },
      ],
    },
    // 蓝色旋转弧
    {
      ty: 4, nm: 'arc', ind: 1, ip: 0, op: 60, st: 0,
      ks: {
        o: { a: 0, k: 100 },
        r: { a: 1, k: [
          { t: 0, s: [0], i: { x: [0.333], y: [0.333] }, o: { x: [0.667], y: [0.667] } },
          { t: 60, s: [360] },
        ] },
        p: { a: 0, k: [60, 60, 0] }, a: { a: 0, k: [0, 0, 0] }, s: { a: 0, k: [100, 100, 100] },
      },
      shapes: [
        { ty: 'el', p: { a: 0, k: [0, 0] }, s: { a: 0, k: [80, 80] } },
        {
          ty: 'st',
          c: { a: 0, k: [0.09, 0.47, 1, 1] },
          o: { a: 0, k: 100 }, w: { a: 0, k: 8 }, lc: 2, lj: 1,
          d: [
            { nm: 'Dash', n: 'd', v: { a: 0, k: 63 } },
            { nm: 'Gap', n: 'g', v: { a: 0, k: 189 } },
          ],
        },
      ],
    },
  ],
}

const DONE_ANIM = {
  v: '5.9.0', fr: 24, ip: 0, op: 36, w: 120, h: 120,
  assets: [],
  layers: [{
    ty: 4, nm: 'check', ind: 1, ip: 0, op: 36, st: 0,
    ks: {
      o: { a: 0, k: 100 }, r: { a: 0, k: 0 },
      p: { a: 0, k: [60, 60, 0] }, a: { a: 0, k: [0, 0, 0] },
      s: { a: 1, k: [
        { t: 0, s: [0, 0, 100], i: { x: [0.34], y: [1.56] }, o: { x: [0.56], y: [0] } },
        { t: 20, s: [100, 100, 100] },
      ] },
    },
    shapes: [
      { ty: 'el', p: { a: 0, k: [0, 0] }, s: { a: 0, k: [70, 70] } },
      { ty: 'fl', c: { a: 0, k: [0.32, 0.77, 0.32, 1] }, o: { a: 0, k: 100 } },
    ],
  }],
}

const ANIM_DATA = { idle: IDLE_ANIM, working: WORKING_ANIM, done: DONE_ANIM }

// ── 文件飞行动画 CSS ───────────────────────────────────────────
const FLY_KEYFRAMES = `
@keyframes agentFileFly {
  0%   { opacity: 1; transform: translate(0, 0) scale(1); }
  75%  { opacity: 1; }
  100% { opacity: 0; transform: translate(var(--tx), var(--ty)) scale(0.7); }
}
`

// ── Agent 卡片 ─────────────────────────────────────────────────
function AgentCard({ agent, state, cardRef }) {
  const borderColor = { working: '#1677ff', done: '#52c41a', idle: '#d9d9d9' }[state]
  const bgColor     = { working: '#e6f4ff', done: '#f6ffed', idle: '#fafafa' }[state]
  const statusText  = { working: '执行中...', done: '完成 ✓', idle: '待机' }[state]
  const statusColor = { working: '#1677ff', done: '#52c41a', idle: '#bbb' }[state]

  return (
    <div
      ref={cardRef}
      style={{
        width: 156,
        borderRadius: 14,
        border: `2px solid ${borderColor}`,
        background: bgColor,
        padding: '16px 10px 12px',
        textAlign: 'center',
        transition: 'border-color 0.3s, background 0.3s, box-shadow 0.3s',
        boxShadow: state === 'working'
          ? '0 0 0 5px rgba(22,119,255,0.12), 0 4px 16px rgba(0,0,0,0.08)'
          : '0 2px 8px rgba(0,0,0,0.06)',
        flexShrink: 0,
      }}
    >
      <Lottie
        animationData={ANIM_DATA[state]}
        loop={state !== 'done'}
        autoplay
        style={{ width: 80, height: 80, margin: '0 auto' }}
      />
      <div style={{ fontWeight: 600, fontSize: 14, marginTop: 6 }}>{agent.name}</div>
      <div style={{ fontSize: 11, color: '#999', marginBottom: 6 }}>{agent.model}</div>
      <div style={{ fontSize: 11, color: statusColor, fontWeight: 500 }}>{statusText}</div>
    </div>
  )
}

// ── 主组件 ────────────────────────────────────────────────────
export default function AgentRunView({ graphId, graph }) {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([])
  const [running, setRunning] = useState(false)
  const [agentStates, setAgentStates] = useState({})
  const [transfers, setTransfers] = useState([])
  const bottomRef = useRef(null)
  const cardRefs = useRef({})

  // 初始化 agent 状态为 idle
  useEffect(() => {
    if (!graph) return
    const init = {}
    graph.agents.forEach(a => { init[a.id] = 'idle' })
    setAgentStates(init)
  }, [graph])

  const resetStates = useCallback(() => {
    if (!graph) return
    const init = {}
    graph.agents.forEach(a => { init[a.id] = 'idle' })
    setAgentStates(init)
    setTransfers([])
  }, [graph])

  const append = useCallback((msg) => {
    setMessages(prev => [...prev, msg])
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
  }, [])

  // 文件传递飞行动画
  const showTransfer = useCallback((fromId, toId, artifact) => {
    const fromEl = cardRefs.current[fromId]
    const toEl = cardRefs.current[toId]
    if (!fromEl || !toEl) return

    const fr = fromEl.getBoundingClientRect()
    const tr = toEl.getBoundingClientRect()
    const fromX = fr.left + fr.width / 2
    const fromY = fr.top + fr.height / 2

    const id = `${Date.now()}-${Math.random()}`
    setTransfers(prev => [...prev, {
      id,
      fromX, fromY,
      tx: tr.left + tr.width / 2 - fromX,
      ty: tr.top + tr.height / 2 - fromY,
      artifact,
    }])
    setTimeout(() => setTransfers(prev => prev.filter(t => t.id !== id)), 950)
  }, [])

  const run = async () => {
    if (!input.trim() || running) return
    const userMsg = input.trim()
    setInput('')
    setMessages([{ role: 'user', content: userMsg }])
    setRunning(true)
    resetStates()

    try {
      await graphApi.run(graphId, userMsg, (chunk) => {
        switch (chunk.type) {
          case 'text':
            // 找到该 node 对应的最后一条 assistant 消息，追加内容
            setMessages(prev => {
              const updated = [...prev]
              for (let i = updated.length - 1; i >= 0; i--) {
                if (updated[i].role === 'assistant' && updated[i].node === chunk.node) {
                  updated[i] = { ...updated[i], content: updated[i].content + chunk.content }
                  return updated
                }
              }
              return updated
            })
            break
          case 'node_start':
            setAgentStates(prev => ({ ...prev, [chunk.node]: 'working' }))
            // 系统提示 + 该节点的 assistant 消息槽（顺序追加，不互相干扰）
            setMessages(prev => [
              ...prev,
              { role: 'system', content: `▶ ${chunk.node_name || chunk.node} 开始执行` },
              { role: 'assistant', content: '', node: chunk.node, node_name: chunk.node_name || chunk.node },
            ])
            break
          case 'node_end':
            setAgentStates(prev => ({ ...prev, [chunk.node]: 'done' }))
            break
          case 'edge':
            if (chunk.artifact) {
              showTransfer(chunk.from, chunk.to, chunk.artifact)
              const toName = graph?.agents.find(a => a.id === chunk.to)?.name || chunk.to
              append({ role: 'system', content: `📄 ${chunk.artifact} → ${toName}` })
            }
            if (chunk.prompt) {
              append({ role: 'system', content: `↪ 已注入下游提示：${chunk.prompt}` })
            }
            break
          case 'tool_start':
            append({ role: 'system', content: `🔧 ${chunk.tool}` })
            break
          case 'tool_end':
            append({ role: 'system', content: `  └ ${String(chunk.result).slice(0, 180)}` })
            break
          default:
            break
        }
      }, () => setRunning(false))
    } catch (e) {
      append({ role: 'error', content: e.message })
      setRunning(false)
    }
  }

  if (!graph) {
    return (
      <div style={{ padding: 32, color: '#aaa', fontSize: 14 }}>
        请先从左侧选择一个 Agent 图
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <style>{FLY_KEYFRAMES}</style>

      {/* Agent 卡片区 */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 20,
        padding: '20px 16px',
        background: '#f7f8fa',
        borderBottom: '1px solid #f0f0f0',
        minHeight: 190,
        alignItems: 'center',
      }}>
        {graph.agents.map(agent => (
          <AgentCard
            key={agent.id}
            agent={agent}
            state={agentStates[agent.id] || 'idle'}
            cardRef={el => { cardRefs.current[agent.id] = el }}
          />
        ))}
        {graph.agents.length === 0 && (
          <Text type="secondary">该图暂无 Agent 节点</Text>
        )}
      </div>

      {/* 消息流 */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px', background: '#fff' }}>
        {messages.length === 0 && (
          <Text type="secondary" style={{ fontSize: 13 }}>输入任务，Agent 团队开始工作...</Text>
        )}
        {messages.map((msg, i) => (
          <div key={i} style={{ marginBottom: 8, display: 'flex', alignItems: 'flex-start', gap: 8 }}>
            <Tag
              color={
                msg.role === 'user' ? 'blue'
                  : msg.role === 'error' ? 'red'
                  : msg.role === 'system' ? 'default'
                  : 'green'
              }
              style={{ flexShrink: 0, marginTop: 2 }}
            >
              {msg.role === 'user' ? '用户'
                : msg.role === 'system' ? '系统'
                : msg.role === 'error' ? '错误'
                : (msg.node_name || msg.node || 'Agent')}
            </Tag>
            <Text style={{
              whiteSpace: 'pre-wrap',
              fontSize: 13,
              color: msg.role === 'user' ? '#1677ff'
                : msg.role === 'error' ? '#ff4d4f'
                : msg.role === 'system' ? '#888'
                : '#333',
            }}>
              {msg.content}
            </Text>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* 输入区 */}
      <div style={{ padding: '12px 16px', borderTop: '1px solid #f0f0f0' }}>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={input}
            onChange={e => setInput(e.target.value)}
            onPressEnter={run}
            placeholder="输入任务，发布给 Agent 团队..."
            disabled={running}
          />
          <Button type="primary" icon={<SendOutlined />} onClick={run} loading={running}>
            发送
          </Button>
        </Space.Compact>
      </div>

      {/* 文件传递飞行徽章（position: fixed，叠加在页面最上层） */}
      {transfers.map(t => (
        <div
          key={t.id}
          style={{
            position: 'fixed',
            left: t.fromX - 32,
            top: t.fromY - 13,
            zIndex: 9999,
            background: '#fff',
            border: '1.5px solid #1677ff',
            borderRadius: 5,
            padding: '2px 8px',
            fontSize: 12,
            color: '#1677ff',
            fontWeight: 500,
            pointerEvents: 'none',
            whiteSpace: 'nowrap',
            boxShadow: '0 2px 8px rgba(22,119,255,0.25)',
            animation: 'agentFileFly 0.85s ease-in-out forwards',
            '--tx': `${t.tx}px`,
            '--ty': `${t.ty}px`,
          }}
        >
          📄 {t.artifact}
        </div>
      ))}
    </div>
  )
}
