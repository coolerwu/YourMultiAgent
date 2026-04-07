/**
 * components/AgentRunner.jsx
 *
 * 运行指定 Agent 图，流式展示输出 + 执行流可视化。
 *
 * 布局：上半部分 = 只读 React Flow 图（节点执行高亮、边触发动画）
 *       下半部分 = 对话消息列表 + 输入框
 *
 * WebSocket 事件处理：
 *   node_start → 节点变蓝（活跃状态）
 *   node_end   → 节点变绿（完成状态）
 *   edge       → 对应边添加动画
 *   text       → 追加到当前 assistant 消息
 *   tool_start → 插入系统提示消息
 *   tool_end   → 插入工具结果消息
 *   done/error → 停止运行状态
 */

import {
  Background,
  Handle,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { SendOutlined } from '@ant-design/icons'
import { Button, Input, Space, Tag, Typography } from 'antd'
import { useCallback, useEffect, useRef, useState } from 'react'
import { graphApi } from '../utils/graphApi'

const { Text } = Typography

// ── 只读 Agent 节点 ───────────────────────────────────────────
function RunnerAgentNode({ data }) {
  const { execState } = data  // 'idle' | 'active' | 'done'
  const borderColor = execState === 'active' ? '#1677ff' : execState === 'done' ? '#52c41a' : '#d9d9d9'
  const bg = execState === 'active' ? '#e6f4ff' : execState === 'done' ? '#f6ffed' : '#fff'
  return (
    <div style={{
      padding: '8px 14px',
      borderRadius: 8,
      border: `2px solid ${borderColor}`,
      background: bg,
      minWidth: 140,
      transition: 'border-color 0.3s, background 0.3s',
    }}>
      <Handle type="target" position={Position.Left} style={{ visibility: 'hidden' }} />
      <div style={{ fontWeight: 600, fontSize: 12 }}>{data.name}</div>
      <div style={{ fontSize: 10, color: '#888' }}>{data.model}</div>
      {execState === 'active' && (
        <div style={{ fontSize: 10, color: '#1677ff', marginTop: 4 }}>● 执行中...</div>
      )}
      {execState === 'done' && (
        <div style={{ fontSize: 10, color: '#52c41a', marginTop: 4 }}>✓ 完成</div>
      )}
      <Handle type="source" position={Position.Right} style={{ visibility: 'hidden' }} />
    </div>
  )
}

const runnerNodeTypes = { agent: RunnerAgentNode }

// ── 主组件 ────────────────────────────────────────────────────
export default function AgentRunner({ graphId, graph }) {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([])
  const [running, setRunning] = useState(false)
  const wsRef = useRef(null)   // 当前 WebSocket 实例，用于组件卸载时关闭
  const bottomRef = useRef(null)

  // 组件卸载时关闭未完成的 WebSocket
  useEffect(() => () => wsRef.current?.close(), [])

  // 执行流可视化用的节点/边状态
  const [flowNodes, setFlowNodes, onFlowNodesChange] = useNodesState([])
  const [flowEdges, setFlowEdges, onFlowEdgesChange] = useEdgesState([])

  // 从 graph 初始化只读流程图
  useEffect(() => {
    if (!graph) { setFlowNodes([]); setFlowEdges([]); return }
    setFlowNodes(
      graph.agents.map((a, i) => ({
        id: a.id,
        type: 'agent',
        position: { x: 60 + i * 200, y: 40 },
        data: { ...a, execState: 'idle' },
        draggable: false,
        selectable: false,
        connectable: false,
      }))
    )
    setFlowEdges(
      graph.edges.map((e, i) => ({
        id: `re-${i}`,
        source: e.from_node,
        target: e.to_node,
        animated: false,
        style: { stroke: '#d9d9d9' },
      }))
    )
  }, [graph])

  // 重置图节点状态（每次新对话前）
  const resetFlowState = useCallback(() => {
    setFlowNodes(ns => ns.map(n => ({ ...n, data: { ...n.data, execState: 'idle' } })))
    setFlowEdges(es => es.map(e => ({ ...e, animated: false, style: { stroke: '#d9d9d9' } })))
  }, [setFlowNodes, setFlowEdges])

  const append = (msg) => {
    setMessages((prev) => [...prev, msg])
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
  }

  const run = () => {
    if (!input.trim() || running) return
    const userMsg = input.trim()
    setInput('')
    append({ role: 'user', content: userMsg })
    setRunning(true)
    resetFlowState()

    // 占位 assistant 消息
    setMessages((prev) => [...prev, { role: 'assistant', content: '', node: '', node_name: '' }])

    wsRef.current = graphApi.run(
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
                node_name: chunk.node_name || last.node_name,
              }
            }
            return updated
          })
        } else if (chunk.type === 'node_start') {
          setFlowNodes(ns => ns.map(n =>
            n.id === chunk.node ? { ...n, data: { ...n.data, execState: 'active' } } : n
          ))
        } else if (chunk.type === 'node_end') {
          setFlowNodes(ns => ns.map(n =>
            n.id === chunk.node ? { ...n, data: { ...n.data, execState: 'done' } } : n
          ))
        } else if (chunk.type === 'edge') {
          setFlowEdges(es => es.map(e =>
            (e.source === chunk.from && e.target === chunk.to)
              ? { ...e, animated: true, style: { stroke: '#1677ff' } }
              : e
          ))
        } else if (chunk.type === 'tool_start') {
          append({ role: 'system', content: `🔧 调用工具：${chunk.tool}` })
        } else if (chunk.type === 'tool_end') {
          append({ role: 'system', content: `✅ 工具结果：${String(chunk.result).slice(0, 200)}` })
        }
      },
      () => setRunning(false),
      (err) => { append({ role: 'error', content: err.message }); setRunning(false) },
    )
  }

  const msgColor = { user: '#1677ff', assistant: '#333', system: '#888', error: '#ff4d4f' }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* 执行流可视化图（仅有 graph 数据时显示） */}
      {graph && flowNodes.length > 0 && (
        <div style={{
          height: 140,
          borderRadius: 8,
          border: '1px solid #f0f0f0',
          background: '#fafafa',
          marginBottom: 8,
          overflow: 'hidden',
        }}>
          <ReactFlow
            nodes={flowNodes}
            edges={flowEdges}
            onNodesChange={onFlowNodesChange}
            onEdgesChange={onFlowEdgesChange}
            nodeTypes={runnerNodeTypes}
            fitView
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={false}
            zoomOnScroll={false}
            panOnDrag={false}
          >
            <Background gap={20} color="#f0f0f0" />
          </ReactFlow>
        </div>
      )}

      {/* 消息列表 */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 16, background: '#fafafa', borderRadius: 8 }}>
        {messages.length === 0 && (
          <Text type="secondary">输入消息，开始与 Agent 对话...</Text>
        )}
        {messages.map((msg, i) => (
          <div key={i} style={{ marginBottom: 12 }}>
            <Space align="start">
              <Tag color={msg.role === 'user' ? 'blue' : msg.role === 'system' ? 'default' : 'green'}>
                {msg.role === 'user' ? '用户' : msg.role === 'system' ? '系统' : (msg.node_name || msg.node || 'Agent')}
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
