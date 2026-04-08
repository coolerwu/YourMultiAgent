/**
 * components/AgentDesigner.jsx
 *
 * 基于 React Flow 的 Agent 图编辑器：
 * - 节点 = Agent（双击编辑配置）
 * - 连线 = 流转边（拖拽 handle 连接）
 * - 右键节点 = 弹出上下文菜单（编辑 / 复制 / 删除确认）
 * - 工具栏：添加节点、保存
 * - 支持 openai_compat provider（base_url / api_key / 自由输入 model）
 * - 支持 work_subdir 字段（Agent 在 Workspace 内的子目录）
 * - 接收 workspaceId / workspaceDefaults，新节点继承 Workspace 默认配置
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
  Button, Dropdown, Form, Input, InputNumber, Menu, Modal,
  Select, Space, Tag, Tooltip, message,
} from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { graphApi, workerApi } from '../utils/graphApi'

const { Option } = Select

const PROVIDERS = [
  { value: 'anthropic', label: 'Anthropic (Claude)' },
  { value: 'openai', label: 'OpenAI (GPT)' },
  { value: 'openai_compat', label: '兼容 OpenAI 协议（DeepSeek / Moonshot 等）' },
]
const PRESET_MODELS = {
  anthropic: ['claude-sonnet-4-6', 'claude-opus-4-6', 'claude-haiku-4-5-20251001'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
}
const DEFAULT_CODEX_MODEL = ''
const DEFAULT_CODEX_MODEL_PLACEHOLDER = '留空则使用 Codex CLI 默认模型'
const MODEL_RUNTIME_OPTIONS = [
  { value: 'llm', label: 'LLM' },
  { value: 'codex', label: 'Codex' },
]

function resolveRuntimeType(agent) {
  return agent?.codex_connection_id ? 'codex' : 'llm'
}
// ── 自定义节点 ────────────────────────────────────────────────
function AgentNode({ data, selected }) {
  const modelLabel = data.codex_connection_name || data.llm_profile_name || data.model
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
      <div style={{ fontSize: 11, color: '#888' }}>{modelLabel}</div>
      {data.llm_profile_name && (
        <div style={{ fontSize: 10, color: '#999', marginTop: 2 }}>🔗 {data.llm_profile_name}</div>
      )}
      {data.codex_connection_name && (
        <div style={{ fontSize: 10, color: '#999', marginTop: 2 }}>🔐 {data.codex_connection_name}</div>
      )}
      {data.work_subdir && (
        <div style={{ fontSize: 10, color: '#aaa', marginTop: 2 }}>📁 {data.work_subdir}</div>
      )}
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
/**
 * @param {object}  graph            当前图 GraphVO，新建时为 null
 * @param {string}  workspaceId      新建图时关联的 Workspace ID
 * @param {object}  workspaceDefaults Workspace 的默认 provider/model/base_url/api_key
 * @param {function} onSaved         保存成功回调
 */
export default function AgentDesigner({ graph, workspaceId, workspaceDefaults, onSaved }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [graphName, setGraphName] = useState(graph?.name ?? '未命名图')
  const [capabilities, setCapabilities] = useState([])
  const [nodeModal, setNodeModal] = useState({ open: false, nodeId: null })
  const [nodeForm] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [optimizingPrompt, setOptimizingPrompt] = useState(false)
  const [optimizingEdgePrompt, setOptimizingEdgePrompt] = useState(false)
  const [contextMenu, setContextMenu] = useState({ open: false, x: 0, y: 0, nodeId: null })
  const [edgeEdit, setEdgeEdit] = useState({
    open: false, x: 0, y: 0, edgeId: null, artifact: '', prompt: '',
  })
  const [promptOptimizer, setPromptOptimizer] = useState({
    open: false,
    goal: '润色当前 Prompt，让表达更清晰、更稳定',
    optimizedPrompt: '',
    reason: '',
  })
  const [edgePromptOptimizer, setEdgePromptOptimizer] = useState({
    open: false,
    goal: '润色当前连线 Prompt，让上下游协作指令更清晰',
    optimizedPrompt: '',
    reason: '',
  })

  const closeContextMenu = () => setContextMenu(m => ({ ...m, open: false }))
  const closeEdgeEdit = () => setEdgeEdit(m => ({ ...m, open: false }))
  const llmProfiles = workspaceDefaults?.llm_profiles ?? []
  const codexConnections = workspaceDefaults?.codex_connections ?? []
  const effectiveWorkspaceId = graph?.workspace_id ?? workspaceId ?? ''

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
        position: { x: 100 + i * 400, y: 150 },
        data: {
          ...a,
          llm_profile_name: llmProfiles.find(profile => profile.id === a.llm_profile_id)?.name ?? '',
          codex_connection_name: codexConnections.find(connection => connection.id === a.codex_connection_id)?.name ?? '',
        },
      }))
    )
    setEdges(
      graph.edges.map((e, i) => ({
        id: `e-${i}`,
        source: e.from_node,
        target: e.to_node,
        label: e.artifact || '始终',
        data: { artifact: e.artifact || '', prompt: e.prompt || '' },
        animated: !e.artifact,
      }))
    )
  }, [graph, llmProfiles, codexConnections])

  // 拖拽连线（默认无 artifact，始终触发）
  const onConnect = useCallback((params) => {
    setEdges(eds => addEdge({
      ...params,
      label: '始终',
      data: { artifact: '', prompt: '' },
      animated: true,
    }, eds))
  }, [setEdges])

  // 点击边 → 弹出编辑框
  const onEdgeClick = useCallback((e, edge) => {
    e.stopPropagation()
    setEdgeEdit({
      open: true,
      x: e.clientX,
      y: e.clientY,
      edgeId: edge.id,
      artifact: edge.data?.artifact ?? '',
      prompt: edge.data?.prompt ?? '',
    })
    closeContextMenu()
  }, [])

  // 保存边：更新 artifact 和 prompt
  const saveEdge = useCallback((artifact, prompt) => {
    setEdges(es => es.map(e => {
      if (e.id !== edgeEdit.edgeId) return e
      return {
        ...e,
        label: artifact || '始终',
        data: { ...e.data, artifact, prompt },
        animated: !artifact,
      }
    }))
    closeEdgeEdit()
  }, [edgeEdit.edgeId, setEdges])

  const getEdgeContext = useCallback(() => {
    const edge = edges.find(item => item.id === edgeEdit.edgeId)
    if (!edge) return null
    const sourceNode = nodes.find(item => item.id === edge.source)
    const targetNode = nodes.find(item => item.id === edge.target)
    return {
      edge,
      sourceNode,
      targetNode,
    }
  }, [edgeEdit.edgeId, edges, nodes])

  // 双击节点 → 编辑弹窗
  const onNodeDoubleClick = useCallback((_, node) => {
    nodeForm.setFieldsValue({
      ...node.data,
      runtime_type: resolveRuntimeType(node.data),
    })
    setNodeModal({ open: true, nodeId: node.id })
    closeContextMenu()
  }, [nodeForm])

  // 右键节点 → 弹出操作菜单
  const onNodeContextMenu = useCallback((e, node) => {
    e.preventDefault()
    e.stopPropagation()
    setContextMenu({ open: true, x: e.clientX, y: e.clientY, nodeId: node.id })
  }, [])

  // 打开编辑弹窗（供菜单调用）
  const openEditModal = useCallback((nodeId) => {
    const node = nodes.find(n => n.id === nodeId)
    if (!node) return
    nodeForm.setFieldsValue({
      ...node.data,
      runtime_type: resolveRuntimeType(node.data),
    })
    setNodeModal({ open: true, nodeId })
  }, [nodes, nodeForm])

  // 复制节点：偏移 (30,30)，自动打开编辑弹窗
  const duplicateNode = useCallback((nodeId) => {
    const src = nodes.find(n => n.id === nodeId)
    if (!src) return
    const newId = `node_${Date.now()}`
    const newNode = {
      ...src,
      id: newId,
      position: { x: src.position.x + 30, y: src.position.y + 30 },
      data: { ...src.data, id: newId, name: src.data.name + '（副本）' },
      selected: false,
    }
    setNodes(ns => [...ns, newNode])
    nodeForm.setFieldsValue({
      ...newNode.data,
      runtime_type: resolveRuntimeType(newNode.data),
    })
    setNodeModal({ open: true, nodeId: newId })
    closeContextMenu()
  }, [nodes, nodeForm, setNodes])

  // 删除确认
  const confirmDelete = useCallback((nodeId) => {
    Modal.confirm({
      title: '确认删除节点？',
      content: '关联的边也将一并删除',
      okType: 'danger',
      okText: '删除',
      cancelText: '取消',
      onOk: () => {
        setNodes(ns => ns.filter(n => n.id !== nodeId))
        setEdges(es => es.filter(e => e.source !== nodeId && e.target !== nodeId))
      },
    })
  }, [setNodes, setEdges])

  // 保存节点编辑
  const saveNode = () => {
    nodeForm.validateFields().then(vals => {
      const currentNode = nodes.find(n => n.id === nodeModal.nodeId)
      const currentData = currentNode?.data ?? {}
      const nextData = {
        ...currentData,
        ...vals,
      }
      delete nextData.runtime_type
      const profile = llmProfiles.find(item => item.id === vals.llm_profile_id)
      const codexConnection = codexConnections.find(item => item.id === vals.codex_connection_id)
      setNodes(ns => ns.map(n =>
        n.id === nodeModal.nodeId
          ? {
            ...n,
            data: {
              ...nextData,
              llm_profile_name: profile?.name ?? '',
              codex_connection_name: codexConnection?.name ?? '',
            },
          }
          : n
      ))
      setNodeModal({ open: false, nodeId: null })
    })
  }

  const openPromptOptimizer = async () => {
    try {
      await nodeForm.validateFields(['name'])
      setPromptOptimizer({
        open: true,
        goal: '润色当前 Prompt，让表达更清晰、更稳定',
        optimizedPrompt: '',
        reason: '',
      })
    } catch (_) {
      // 校验由 Form 自己展示
    }
  }

  const handlePromptOptimize = async () => {
    const values = nodeForm.getFieldsValue()
    setOptimizingPrompt(true)
    try {
      const result = await graphApi.optimizePrompt({
        name: values.name,
        system_prompt: values.system_prompt ?? '',
        goal: promptOptimizer.goal,
        workspace_id: effectiveWorkspaceId,
        provider: values.provider ?? workspaceDefaults?.default_provider ?? 'anthropic',
        model: values.model ?? workspaceDefaults?.default_model ?? 'claude-sonnet-4-6',
        temperature: 0.2,
        max_tokens: values.max_tokens ?? 4096,
        tools: values.tools ?? [],
        llm_profile_id: values.llm_profile_id ?? '',
        codex_connection_id: values.codex_connection_id ?? '',
        base_url: values.base_url ?? '',
        api_key: values.api_key ?? '',
      })
      setPromptOptimizer(prev => ({
        ...prev,
        optimizedPrompt: result.optimized_prompt ?? '',
        reason: result.reason ?? '',
      }))
    } catch (e) {
      message.error(e.message)
    } finally {
      setOptimizingPrompt(false)
    }
  }

  const openEdgePromptOptimizer = () => {
    setEdgePromptOptimizer({
      open: true,
      goal: '润色当前连线 Prompt，让上下游协作指令更清晰',
      optimizedPrompt: '',
      reason: '',
    })
  }

  const handleEdgePromptOptimize = async () => {
    const context = getEdgeContext()
    if (!context) {
      message.warning('未找到当前连线')
      return
    }
    const targetData = context.targetNode?.data ?? {}
    setOptimizingEdgePrompt(true)
    try {
      const result = await graphApi.optimizePrompt({
        name: targetData.name ?? '未命名 Agent',
        system_prompt: edgeEdit.prompt ?? '',
        prompt_kind: 'edge_prompt',
        goal: edgePromptOptimizer.goal,
        workspace_id: effectiveWorkspaceId,
        source_name: context.sourceNode?.data?.name ?? '',
        target_name: targetData.name ?? '',
        artifact: edgeEdit.artifact ?? '',
        provider: targetData.provider ?? workspaceDefaults?.default_provider ?? 'anthropic',
        model: targetData.model ?? workspaceDefaults?.default_model ?? 'claude-sonnet-4-6',
        temperature: 0.2,
        max_tokens: targetData.max_tokens ?? 4096,
        tools: targetData.tools ?? [],
        llm_profile_id: targetData.llm_profile_id ?? '',
        codex_connection_id: targetData.codex_connection_id ?? '',
        base_url: targetData.base_url ?? '',
        api_key: targetData.api_key ?? '',
      })
      setEdgePromptOptimizer(prev => ({
        ...prev,
        optimizedPrompt: result.optimized_prompt ?? '',
        reason: result.reason ?? '',
      }))
    } catch (e) {
      message.error(e.message)
    } finally {
      setOptimizingEdgePrompt(false)
    }
  }

  // 添加新节点（继承 Workspace 默认值）
  const addNode = () => {
    const id = `node_${Date.now()}`
    const defaults = workspaceDefaults ?? {}
    const newNode = {
      id,
      type: 'agent',
      position: { x: 100 + nodes.length * 400, y: 150 },
      data: {
        id,
        name: '新 Agent',
        llm_profile_id: llmProfiles[0]?.id ?? '',
        llm_profile_name: llmProfiles[0]?.name ?? '',
        codex_connection_id: '',
        codex_connection_name: '',
        provider: defaults.default_provider ?? 'anthropic',
        model: defaults.default_model ?? 'claude-sonnet-4-6',
        base_url: defaults.default_base_url ?? '',
        api_key: defaults.default_api_key ?? '',
        system_prompt: '你是一个助手。',
        temperature: 0.7,
        max_tokens: 4096,
        tools: [],
        work_subdir: '',
      },
    }
    setNodes(ns => [...ns, newNode])
    nodeForm.setFieldsValue({ ...newNode.data, runtime_type: 'llm' })
    setNodeModal({ open: true, nodeId: id })
  }

  // 保存到后端
  const handleSave = async () => {
    if (!graphName.trim()) { message.warning('请输入图名称'); return }
    if (nodes.length === 0) { message.warning('至少需要一个节点'); return }

    if (!effectiveWorkspaceId) { message.warning('请先在 Workspace 下创建或选择智能体'); return }

    const payload = {
      name: graphName,
      entry_node: nodes[0].id,
      workspace_id: effectiveWorkspaceId,
      agents: nodes.map(n => ({ ...n.data, id: n.id })),
      edges: edges.map(e => ({
        from_node: e.source,
        to_node: e.target,
        artifact: e.data?.artifact ?? '',
        prompt: e.data?.prompt ?? '',
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
          双击节点编辑 · 右键节点操作 · 拖拽 handle 连线
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
          onEdgeClick={onEdgeClick}
          onPaneClick={() => { closeContextMenu(); closeEdgeEdit() }}
          onNodeClick={() => { closeContextMenu(); closeEdgeEdit() }}
          onMoveStart={() => { closeContextMenu(); closeEdgeEdit() }}
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
        width={560}
      >
        <Form form={nodeForm} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>

          <Form.Item name="runtime_type" label="模型类型" initialValue="llm" rules={[{ required: true }]}>
            <Select
              options={MODEL_RUNTIME_OPTIONS}
              onChange={(value) => {
                if (value === 'codex') {
                  nodeForm.setFieldsValue({
                    llm_profile_id: '',
                    model: DEFAULT_CODEX_MODEL,
                  })
                  return
                }
                nodeForm.setFieldValue('codex_connection_id', '')
              }}
            />
          </Form.Item>

          <Form.Item noStyle shouldUpdate={(p, c) => (
            p.runtime_type !== c.runtime_type
            || p.llm_profile_id !== c.llm_profile_id
            || p.codex_connection_id !== c.codex_connection_id
            || p.provider !== c.provider
          )}>
            {({ getFieldValue }) => {
              const runtimeType = getFieldValue('runtime_type') ?? 'llm'
              if (runtimeType === 'codex') {
                return (
                  <>
                    <Form.Item
                      name="codex_connection_id"
                      label="Codex 登录连接"
                      extra="引用全局共享的 Codex 登录连接；当前仅完成配置建模，服务端运行时尚未接入真实登录通道"
                    >
                      <Select
                        allowClear
                        placeholder={codexConnections.length ? '选择 Codex 登录连接' : '当前 Workspace 暂无 Codex 登录连接'}
                      >
                        {codexConnections.map(connection => (
                          <Option key={connection.id} value={connection.id}>{connection.name}</Option>
                        ))}
                      </Select>
                    </Form.Item>
                    <Form.Item
                      name="model"
                      label="Codex 模型"
                      extra="建议留空，直接使用当前 Codex CLI 账号默认可用模型；只有明确知道模型权限时再手动填写"
                    >
                      <Input placeholder={DEFAULT_CODEX_MODEL_PLACEHOLDER} />
                    </Form.Item>
                  </>
                )
              }
              const provider = getFieldValue('provider')
              return (
                <>
                  <Form.Item
                    name="llm_profile_id"
                    label="通用 LLM 配置"
                    extra="引用当前 Workspace 预定义的接口和 Token；留空则使用节点自定义配置"
                  >
                    <Select
                      allowClear
                      placeholder={llmProfiles.length ? '选择通用配置' : '当前 Workspace 暂无通用配置'}
                    >
                      {llmProfiles.map(profile => (
                        <Option key={profile.id} value={profile.id}>{profile.name}</Option>
                      ))}
                    </Select>
                  </Form.Item>

                  {getFieldValue('llm_profile_id') ? null : (
                    <>
                      <Form.Item name="provider" label="Provider" rules={[{ required: true }]}>
                        <Select>
                          {PROVIDERS.map(p => <Option key={p.value} value={p.value}>{p.label}</Option>)}
                        </Select>
                      </Form.Item>

                      <Form.Item name="model" label="模型" rules={[{ required: true }]}>
                        {provider === 'openai_compat' ? (
                          <Input placeholder="例如：deepseek-chat" />
                        ) : (
                          <Select>
                            {(PRESET_MODELS[provider] ?? []).map(m =>
                              <Option key={m} value={m}>{m}</Option>
                            )}
                          </Select>
                        )}
                      </Form.Item>

                      {provider === 'openai_compat' && (
                        <>
                          <Form.Item
                            name="base_url"
                            label="Base URL"
                            rules={[{ required: true, message: '请输入 base_url' }]}
                          >
                            <Input placeholder="https://api.deepseek.com/v1" />
                          </Form.Item>
                          <Form.Item
                            name="api_key"
                            label="API Key（选填）"
                            extra="留空则使用 Workspace 或环境变量中的 key"
                          >
                            <Input.Password placeholder="sk-..." />
                          </Form.Item>
                        </>
                      )}
                    </>
                  )}
                </>
              )
            }}
          </Form.Item>

          <Form.Item
            name="system_prompt"
            label={(
              <Space size={8}>
                <span>System Prompt</span>
                <Button size="small" onClick={openPromptOptimizer}>AI 优化</Button>
              </Space>
            )}
            rules={[{ required: true }]}
          >
            <Input.TextArea rows={4} />
          </Form.Item>

          <Form.Item
            name="work_subdir"
            label="工作子目录"
            extra="相对于 Workspace 根目录，留空则使用 Agent 名称"
          >
            <Input placeholder="例如：writer（默认与 Agent 名称相同）" />
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

      <Modal
        title="AI 优化 System Prompt"
        open={promptOptimizer.open}
        onCancel={() => setPromptOptimizer(prev => ({ ...prev, open: false }))}
        width={680}
        footer={[
          <Button
            key="cancel"
            onClick={() => setPromptOptimizer(prev => ({ ...prev, open: false }))}
          >
            关闭
          </Button>,
          <Button
            key="optimize"
            type="primary"
            loading={optimizingPrompt}
            onClick={handlePromptOptimize}
          >
            生成建议
          </Button>,
          <Button
            key="apply"
            type="primary"
            disabled={!promptOptimizer.optimizedPrompt}
            onClick={() => {
              nodeForm.setFieldValue('system_prompt', promptOptimizer.optimizedPrompt)
              setPromptOptimizer(prev => ({ ...prev, open: false }))
            }}
          >
            替换当前 Prompt
          </Button>,
        ]}
      >
        <Space direction="vertical" style={{ width: '100%' }} size={16}>
          <div>
            <div style={{ marginBottom: 8, fontSize: 12, color: '#666' }}>优化目标</div>
            <Select
              style={{ width: '100%' }}
              value={promptOptimizer.goal}
              onChange={(goal) => setPromptOptimizer(prev => ({ ...prev, goal }))}
              options={[
                { value: '润色当前 Prompt，让表达更清晰、更稳定', label: '润色表达' },
                { value: '增强约束，让任务边界、输出要求和工具使用规则更明确', label: '增强约束' },
                { value: '按当前 Agent 角色重写 Prompt，让职责、输入输出和协作方式更完整', label: '按角色重写' },
              ]}
            />
          </div>
          <div>
            <div style={{ marginBottom: 8, fontSize: 12, color: '#666' }}>优化建议</div>
            <Input.TextArea
              rows={10}
              readOnly
              value={promptOptimizer.optimizedPrompt}
              placeholder="点击“生成建议”后，这里会显示优化后的 Prompt。"
            />
          </div>
          <div>
            <div style={{ marginBottom: 8, fontSize: 12, color: '#666' }}>说明</div>
            <Input.TextArea
              rows={3}
              readOnly
              value={promptOptimizer.reason}
              placeholder="这里会显示本次优化的简短说明。"
            />
          </div>
        </Space>
      </Modal>

      <Modal
        title="AI 优化连线 Prompt"
        open={edgePromptOptimizer.open}
        onCancel={() => setEdgePromptOptimizer(prev => ({ ...prev, open: false }))}
        width={680}
        footer={[
          <Button
            key="cancel"
            onClick={() => setEdgePromptOptimizer(prev => ({ ...prev, open: false }))}
          >
            关闭
          </Button>,
          <Button
            key="optimize"
            type="primary"
            loading={optimizingEdgePrompt}
            onClick={handleEdgePromptOptimize}
          >
            生成建议
          </Button>,
          <Button
            key="apply"
            type="primary"
            disabled={!edgePromptOptimizer.optimizedPrompt}
            onClick={() => {
              setEdgeEdit(prev => ({
                ...prev,
                prompt: edgePromptOptimizer.optimizedPrompt,
              }))
              setEdgePromptOptimizer(prev => ({ ...prev, open: false }))
            }}
          >
            替换当前 Prompt
          </Button>,
        ]}
      >
        <Space direction="vertical" style={{ width: '100%' }} size={16}>
          <div>
            <div style={{ marginBottom: 8, fontSize: 12, color: '#666' }}>优化目标</div>
            <Select
              style={{ width: '100%' }}
              value={edgePromptOptimizer.goal}
              onChange={(goal) => setEdgePromptOptimizer(prev => ({ ...prev, goal }))}
              options={[
                { value: '润色当前连线 Prompt，让上下游协作指令更清晰', label: '润色表达' },
                { value: '增强连线 Prompt 的约束，让下游输入、动作和输出要求更明确', label: '增强约束' },
                { value: '按上下游职责重写连线 Prompt，让交接意图更完整', label: '按协作重写' },
              ]}
            />
          </div>
          <div>
            <div style={{ marginBottom: 8, fontSize: 12, color: '#666' }}>优化建议</div>
            <Input.TextArea
              rows={8}
              readOnly
              value={edgePromptOptimizer.optimizedPrompt}
              placeholder="点击“生成建议”后，这里会显示优化后的连线 Prompt。"
            />
          </div>
          <div>
            <div style={{ marginBottom: 8, fontSize: 12, color: '#666' }}>说明</div>
            <Input.TextArea
              rows={3}
              readOnly
              value={edgePromptOptimizer.reason}
              placeholder="这里会显示本次优化的简短说明。"
            />
          </div>
        </Space>
      </Modal>

      {/* 边 artifact / prompt 编辑浮层 */}
      {edgeEdit.open && (
        <div style={{
          position: 'fixed',
          left: edgeEdit.x,
          top: edgeEdit.y,
          zIndex: 9999,
          background: '#fff',
          border: '1px solid #d9d9d9',
          borderRadius: 6,
          padding: '10px 12px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          width: 280,
        }}>
          <div style={{ fontSize: 12, color: '#666' }}>触发文件</div>
          <Input
            autoFocus
            size="small"
            placeholder="留空=始终触发"
            value={edgeEdit.artifact}
            onChange={e => setEdgeEdit(v => ({ ...v, artifact: e.target.value }))}
          />
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <div style={{ fontSize: 12, color: '#666' }}>传递给下游的 Prompt</div>
            <Button size="small" onClick={openEdgePromptOptimizer}>AI 优化</Button>
          </div>
          <Input.TextArea
            size="small"
            rows={3}
            placeholder="可选，作为下一节点的补充指令"
            value={edgeEdit.prompt}
            onChange={e => setEdgeEdit(v => ({ ...v, prompt: e.target.value }))}
            onPressEnter={e => {
              if (!e.shiftKey) {
                e.preventDefault()
                saveEdge(edgeEdit.artifact.trim(), edgeEdit.prompt.trim())
              }
            }}
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <Button size="small" onClick={closeEdgeEdit}>取消</Button>
            <Button
              size="small"
              type="primary"
              onClick={() => saveEdge(edgeEdit.artifact.trim(), edgeEdit.prompt.trim())}
            >
              保存
            </Button>
          </div>
          <div style={{ fontSize: 11, color: '#999' }}>
            留空 artifact 表示默认流转边；有 artifact 时仅在根目录存在该文件时触发。
          </div>
        </div>
      )}

      {/* 右键上下文菜单 */}
      <Dropdown
        open={contextMenu.open}
        onOpenChange={(v) => !v && closeContextMenu()}
        trigger={[]}
        dropdownRender={() => (
          <div style={{ position: 'fixed', left: contextMenu.x, top: contextMenu.y, zIndex: 9999 }}>
            <Menu
              items={[
                {
                  key: 'edit',
                  label: '✏️ 编辑',
                  onClick: () => { openEditModal(contextMenu.nodeId); closeContextMenu() },
                },
                {
                  key: 'duplicate',
                  label: '📋 复制节点',
                  onClick: () => duplicateNode(contextMenu.nodeId),
                },
                { key: 'divider', type: 'divider' },
                {
                  key: 'delete',
                  label: <span style={{ color: '#ff4d4f' }}>🗑️ 删除</span>,
                  onClick: () => { confirmDelete(contextMenu.nodeId); closeContextMenu() },
                },
              ]}
            />
          </div>
        )}
      >
        <div style={{ position: 'fixed', left: contextMenu.x, top: contextMenu.y, width: 0, height: 0 }} />
      </Dropdown>
    </div>
  )
}
