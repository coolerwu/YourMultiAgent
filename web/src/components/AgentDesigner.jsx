/**
 * components/AgentDesigner.jsx
 *
 * 基于 React Flow 的 Agent 图编辑器：
 * - 节点 = Agent（双击编辑配置）
 * - 连线 = 流转边（拖拽 handle 连接）
 * - 右键节点 = 删除
 * - 工具栏：添加节点、保存
 */

import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  Button, Form, Input, InputNumber, Modal,
  Select, Space, Tag, Tooltip, message,
} from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { graphApi, workerApi } from '../utils/graphApi'

const { Option } = Select

const PROVIDERS = [
  { value: 'anthropic', label: 'Anthropic (Claude)' },
  { value: 'openai', label: 'OpenAI (GPT)' },
]
const MODELS = {
  anthropic: ['claude-sonnet-4-6', 'claude-opus-4-6', 'claude-haiku-4-5-20251001'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
}
const EDGE_CONDITIONS = [
  { value: 'always', label: '始终' },
  { value: 'on_success', label: '成功时' },
  { value: 'on_failure', label: '失败时' },
]

// ── 自定义节点 ────────────────────────────────────────────────
function AgentNode({ data, selected }) {
  return (
    <div style={{
      padding: '10px 16px',
      borderRadius: 8,
      border: `2px solid ${selected ? '#1677ff' : '#d9d9d9'}`,
      background: '#fff',
      minWidth: 160,
      boxShadow: selected ? '0 0 0 3px #e6f4ff' : '0 2px 8px rgba(0,0,0,0.08)',
      cursor: 'pointer',
    }}>
      <Handle type="target" position={Position.Left} />
      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{data.name}</div>
      <div style={{ fontSize: 11, color: '#888' }}>{data.model}</div>
      {data.tools?.length > 0 && (
        <div style={{ marginTop: 6 }}>
          {data.tools.map(t => <Tag key={t} style={{ fontSize: 10 }}>{t}</Tag>)}
        </div>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

const nodeTypes = { agent: AgentNode }

// ── 主组件 ────────────────────────────────────────────────────
export default function AgentDesigner({ graph, onSaved }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [graphName, setGraphName] = useState(graph?.name ?? '未命名图')
  const [capabilities, setCapabilities] = useState([])
  const [nodeModal, setNodeModal] = useState({ open: false, nodeId: null })
  const [nodeForm] = Form.useForm()
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    workerApi.listCapabilities().then(setCapabilities).catch(() => {})
  }, [])

  // 从 graph 数据初始化节点和边
  useEffect(() => {
    if (!graph) { setNodes([]); setEdges([]); setGraphName('未命名图'); return }
    setGraphName(graph.name)
    setNodes(
      graph.agents.map((a, i) => ({
        id: a.id,
        type: 'agent',
        position: { x: 100 + i * 220, y: 150 },
        data: { ...a },
      }))
    )
    setEdges(
      graph.edges.map((e, i) => ({
        id: `e-${i}`,
        source: e.from_node,
        target: e.to_node,
        label: EDGE_CONDITIONS.find(c => c.value === e.condition)?.label ?? '',
        data: { condition: e.condition },
        animated: e.condition === 'always',
      }))
    )
  }, [graph])

  // 拖拽连线
  const onConnect = useCallback((params) => {
    setEdges(eds => addEdge({
      ...params,
      label: '始终',
      data: { condition: 'always' },
      animated: true,
    }, eds))
  }, [setEdges])

  // 双击节点 → 编辑弹窗
  const onNodeDoubleClick = useCallback((_, node) => {
    nodeForm.setFieldsValue(node.data)
    setNodeModal({ open: true, nodeId: node.id })
  }, [nodeForm])

  // 右键节点 → 删除
  const onNodeContextMenu = useCallback((e, node) => {
    e.preventDefault()
    setNodes(ns => ns.filter(n => n.id !== node.id))
    setEdges(es => es.filter(e => e.source !== node.id && e.target !== node.id))
  }, [setNodes, setEdges])

  // 保存节点编辑
  const saveNode = () => {
    nodeForm.validateFields().then(vals => {
      setNodes(ns => ns.map(n =>
        n.id === nodeModal.nodeId ? { ...n, data: { ...n.data, ...vals } } : n
      ))
      setNodeModal({ open: false, nodeId: null })
    })
  }

  // 添加新节点
  const addNode = () => {
    const id = `node_${Date.now()}`
    const newNode = {
      id,
      type: 'agent',
      position: { x: 100 + nodes.length * 220, y: 150 },
      data: {
        id,
        name: '新 Agent',
        provider: 'anthropic',
        model: 'claude-sonnet-4-6',
        system_prompt: '你是一个助手。',
        temperature: 0.7,
        max_tokens: 4096,
        tools: [],
      },
    }
    setNodes(ns => [...ns, newNode])
    // 新节点直接打开编辑
    nodeForm.setFieldsValue(newNode.data)
    setNodeModal({ open: true, nodeId: id })
  }

  // 保存到后端
  const handleSave = async () => {
    if (!graphName.trim()) { message.warning('请输入图名称'); return }
    if (nodes.length === 0) { message.warning('至少需要一个节点'); return }

    const payload = {
      name: graphName,
      entry_node: nodes[0].id,   // 最左侧节点为入口
      agents: nodes.map(n => ({ ...n.data, id: n.id })),
      edges: edges.map(e => ({
        from_node: e.source,
        to_node: e.target,
        condition: e.data?.condition ?? 'always',
      })),
    }
    setSaving(true)
    try {
      const saved = graph?.id
        ? await graphApi.update(graph.id, payload)
        : await graphApi.create(payload)
      message.success('保存成功')
      onSaved?.(saved)
    } catch (e) {
      message.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column' }}>
      {/* 工具栏 */}
      <Space style={{ padding: '8px 16px', borderBottom: '1px solid #f0f0f0' }}>
        <Input
          value={graphName}
          onChange={e => setGraphName(e.target.value)}
          style={{ width: 200 }}
          placeholder="图名称"
        />
        <Button onClick={addNode}>+ 添加节点</Button>
        <Button type="primary" loading={saving} onClick={handleSave}>保存</Button>
        <span style={{ color: '#999', fontSize: 12 }}>
          双击节点编辑 · 右键节点删除 · 拖拽 handle 连线
        </span>
      </Space>

      {/* 画布 */}
      <div style={{ flex: 1 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeDoubleClick={onNodeDoubleClick}
          onNodeContextMenu={onNodeContextMenu}
          nodeTypes={nodeTypes}
          fitView
        >
          <Background />
          <Controls />
          <MiniMap nodeColor={() => '#1677ff'} />
        </ReactFlow>
      </div>

      {/* 节点编辑弹窗 */}
      <Modal
        title="编辑 Agent"
        open={nodeModal.open}
        onOk={saveNode}
        onCancel={() => setNodeModal({ open: false, nodeId: null })}
        width={520}
      >
        <Form form={nodeForm} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="provider" label="Provider" rules={[{ required: true }]}>
            <Select>
              {PROVIDERS.map(p => <Option key={p.value} value={p.value}>{p.label}</Option>)}
            </Select>
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(p, c) => p.provider !== c.provider}>
            {({ getFieldValue }) => (
              <Form.Item name="model" label="模型" rules={[{ required: true }]}>
                <Select>
                  {(MODELS[getFieldValue('provider')] ?? []).map(m =>
                    <Option key={m} value={m}>{m}</Option>
                  )}
                </Select>
              </Form.Item>
            )}
          </Form.Item>
          <Form.Item name="system_prompt" label="System Prompt" rules={[{ required: true }]}>
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="temperature" label="Temperature" initialValue={0.7}>
            <InputNumber min={0} max={2} step={0.1} style={{ width: 100 }} />
          </Form.Item>
          <Form.Item name="tools" label="工具（capability）">
            <Select mode="multiple" placeholder="选择允许使用的工具">
              {capabilities.map(c => (
                <Option key={c.name} value={c.name}>
                  <Tooltip title={c.description}>{c.name}</Tooltip>
                </Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
