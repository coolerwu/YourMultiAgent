import { PlusOutlined } from '@ant-design/icons'
import { Button, Card, Input, Modal, Space, Typography, message } from 'antd'
import { useEffect, useMemo, useRef, useState } from 'react'
import { graphApi, workerApi } from '../utils/graphApi'
import { workspaceApi } from '../utils/workspaceApi'
import AgentEditorPanel from './AgentEditorPanel'
import AgentSummaryCard, { WorkerCardActions } from './AgentSummaryCard'
import {
  emptyAgent,
  normalizeWorkerOrder,
  resolveLlmDisplay,
  sortWorkers,
  validateLlmBinding,
} from './agentEditorUtils'

const { Text } = Typography

function roleKey(selection) {
  return selection.type === 'coordinator' ? 'coordinator' : `worker:${selection.index}`
}

export default function WorkspaceOrchestrationEditor({ workspace, onSaved }) {
  const isChat = workspace?.kind === 'chat'
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [capabilities, setCapabilities] = useState([])
  const [coordinator, setCoordinator] = useState(emptyAgent(workspace, 'coordinator'))
  const [workers, setWorkers] = useState([])
  const coordinatorRef = useRef(coordinator)
  const workersRef = useRef(workers)
  const [selectedRole, setSelectedRole] = useState({ type: 'coordinator', index: -1 })
  const [generatingWorker, setGeneratingWorker] = useState(false)
  const [workerGenerator, setWorkerGenerator] = useState({
    open: false,
    goal: '',
    reason: '',
  })
  const codexConnections = workspace?.codex_connections ?? []

  useEffect(() => {
    workerApi.listCapabilities().then(setCapabilities).catch(() => {})
  }, [])

  useEffect(() => {
    if (!workspace?.id) return
    setLoading(true)
    workspaceApi.getOrchestration(workspace.id)
      .then((result) => {
        const nextCoordinator = result.coordinator ?? emptyAgent(workspace, 'coordinator')
        const nextWorkers = sortWorkers(result.workers ?? [])
        coordinatorRef.current = nextCoordinator
        workersRef.current = nextWorkers
        setCoordinator(nextCoordinator)
        setWorkers(nextWorkers)
        setSelectedRole({ type: 'coordinator', index: -1 })
      })
      .catch((e) => message.error(e.message))
      .finally(() => setLoading(false))
  }, [workspace])

  const selectedAgent = useMemo(() => {
    if (selectedRole.type === 'coordinator') return coordinator
    return workers[selectedRole.index] ?? null
  }, [coordinator, selectedRole, workers])

  const handleAgentChange = (nextAgent) => {
    if (selectedRole.type === 'coordinator') {
      coordinatorRef.current = nextAgent
      setCoordinator(nextAgent)
      return
    }
    setWorkers((prev) => {
      const nextWorkers = prev.map((item, index) => (
        index === selectedRole.index ? { ...nextAgent, order: item.order } : item
      ))
      workersRef.current = nextWorkers
      return nextWorkers
    })
  }

  const openWorkerGenerator = () => {
    setWorkerGenerator({ open: true, goal: '', reason: '' })
  }

  const generateWorker = async () => {
    if (!workerGenerator.goal.trim()) {
      message.warning('请先描述想要的 Worker')
      return
    }
    setGeneratingWorker(true)
    try {
      const result = await graphApi.generateWorker({
        workspace_id: workspace?.id ?? '',
        user_goal: workerGenerator.goal.trim(),
        coordinator_name: coordinator.name,
        coordinator_prompt: coordinator.system_prompt,
        existing_worker_names: workers.map((item) => item.name),
        available_tools: capabilities.map((item) => item.name),
        provider: coordinator.provider ?? 'anthropic',
        model: coordinator.model ?? '',
        llm_profile_id: coordinator.llm_profile_id ?? '',
        codex_connection_id: coordinator.codex_connection_id ?? '',
        base_url: coordinator.base_url ?? '',
        api_key: coordinator.api_key ?? '',
      })
      const generatedWorkers = (result.workers ?? []).map((item, index) => ({
        ...item,
        id: item.id || `worker_${Date.now()}_${index}`,
        order: workers.length + index + 1,
      }))
      setWorkers((prev) => {
        const nextWorkers = normalizeWorkerOrder([...prev, ...generatedWorkers])
        workersRef.current = nextWorkers
        return nextWorkers
      })
      if (generatedWorkers.length > 0) {
        setSelectedRole({ type: 'worker', index: workers.length })
      }
      setWorkerGenerator({
        open: false,
        goal: '',
        reason: result.reason ?? '',
      })
      message.success(result.reason || `已生成 ${generatedWorkers.length} 个 Worker 草稿`)
    } catch (e) {
      message.error(e.message)
    } finally {
      setGeneratingWorker(false)
    }
  }

  const addWorker = () => {
    const nextWorker = emptyAgent(workspace, 'worker')
    setWorkers((prev) => {
      const nextWorkers = normalizeWorkerOrder([
        ...prev,
        { ...nextWorker, id: nextWorker.id || `worker_${Date.now()}`, order: prev.length + 1 },
      ])
      workersRef.current = nextWorkers
      return nextWorkers
    })
    setSelectedRole({ type: 'worker', index: workers.length })
  }

  const moveWorker = (index, direction) => {
    setWorkers((prev) => {
      const next = [...prev]
      const target = index + direction
      if (target < 0 || target >= next.length) return prev
      const selectedWorkerId = selectedRole.type === 'worker' ? prev[selectedRole.index]?.id : ''
      ;[next[index], next[target]] = [next[target], next[index]]
      const nextWorkers = normalizeWorkerOrder(next)
      workersRef.current = nextWorkers
      if (selectedWorkerId) {
        const nextIndex = nextWorkers.findIndex((item) => item.id === selectedWorkerId)
        if (nextIndex >= 0) {
          setSelectedRole({ type: 'worker', index: nextIndex })
        }
      }
      return nextWorkers
    })
  }

  const removeWorker = (index) => {
    setWorkers((prev) => {
      const removedWorkerId = prev[index]?.id
      const nextWorkers = normalizeWorkerOrder(prev.filter((_, itemIndex) => itemIndex !== index))
      workersRef.current = nextWorkers
      if (selectedRole.type === 'worker') {
        const nextIndex = nextWorkers.findIndex((item) => item.id === removedWorkerId)
        if (nextIndex >= 0) {
          setSelectedRole({ type: 'worker', index: nextIndex })
        } else if (nextWorkers.length > 0) {
          setSelectedRole({ type: 'worker', index: Math.min(index, nextWorkers.length - 1) })
        } else {
          setSelectedRole({ type: 'coordinator', index: -1 })
        }
      }
      return nextWorkers
    })
  }

  const persist = async () => {
    if (!workspace?.id) return
    const bindingError = [
      validateLlmBinding(coordinatorRef.current, workspace),
      ...workersRef.current.map((item) => validateLlmBinding(item, workspace)),
    ].find(Boolean)
    if (bindingError) {
      message.error(bindingError)
      return
    }
    setSaving(true)
    try {
      const nextWorkers = normalizeWorkerOrder(workersRef.current)
      workersRef.current = nextWorkers
      setWorkers(nextWorkers)
      const nextCoordinator = coordinatorRef.current
      await workspaceApi.updateOrchestration(workspace.id, {
        coordinator: { ...nextCoordinator, order: 0 },
        workers: nextWorkers,
      })
      message.success('编排配置已保存')
      onSaved?.()
    } catch (e) {
      message.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  if (!selectedAgent) {
    return null
  }

  return (
    <div style={{ padding: 20 }}>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: isChat ? '1fr' : '320px minmax(0, 1fr)',
            gap: 16,
            alignItems: 'start',
          }}
        >
          {!isChat ? (
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Card loading={loading} title="角色列表">
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <AgentSummaryCard
                    title={coordinator.name}
                    subtitle={resolveLlmDisplay(coordinator, workspace)}
                    description={coordinator.work_subdir || 'coordinator'}
                    tools={coordinator.tools ?? []}
                    active={selectedRole.type === 'coordinator'}
                    onClick={() => setSelectedRole({ type: 'coordinator', index: -1 })}
                  />

                  {workers.length === 0 ? <Text type="secondary">当前还没有 Worker</Text> : null}
                  {workers.map((worker, index) => (
                    <AgentSummaryCard
                      key={worker.id}
                      title={`#${worker.order || index + 1} ${worker.name}`}
                      subtitle={resolveLlmDisplay(worker, workspace)}
                      description={`目录：${worker.work_subdir || worker.name}`}
                      tools={worker.tools ?? []}
                      active={selectedRole.type === 'worker' && selectedRole.index === index}
                      onClick={() => setSelectedRole({ type: 'worker', index })}
                      extra={(
                        <WorkerCardActions
                          index={index}
                          total={workers.length}
                          onMoveUp={() => moveWorker(index, -1)}
                          onMoveDown={() => moveWorker(index, 1)}
                          onDelete={() => removeWorker(index)}
                        />
                      )}
                    />
                  ))}
                </Space>
              </Card>

              <Card
                size="small"
                title="Worker 操作"
                extra={(
                  <Space>
                    <Button onClick={openWorkerGenerator}>AI 生成</Button>
                    <Button icon={<PlusOutlined />} onClick={addWorker}>新增 Worker</Button>
                  </Space>
                )}
              >
                <Text type="secondary">点击左侧角色卡片后，右侧会直接切换到对应角色的编辑器。</Text>
              </Card>

              <Card size="small" title="共享约定">
                <Space direction="vertical" size={4}>
                  <Text>主控智能体负责拆解任务，并把交接规则明确给 Worker。</Text>
                  <Text>共享交接物统一写入当前 Workspace 的 `shared/` 目录，例如 `workspace/&lt;workspace_name&gt;/shared/`。</Text>
                  <Text>Worker 私有工作内容写入各自 `work_subdir/` 根目录。</Text>
                  <Text>不要把 Worker 私有过程文件当成默认交接物。</Text>
                </Space>
              </Card>
            </Space>
          ) : null}

          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            {isChat ? (
              <Card loading={loading} size="small" title="单聊说明">
                <Space direction="vertical" size={4}>
                  <Text>当前目录中的历史会话、compact 摘要和 memory 会持续复用。</Text>
                  <Text>输出文件或中间结果统一写入当前目录或其子目录，并明确告知路径。</Text>
                </Space>
              </Card>
            ) : null}

            <AgentEditorPanel
              key={roleKey(selectedRole)}
              workspace={workspace}
              role={selectedRole.type}
              agent={selectedAgent}
              capabilities={capabilities}
              codexConnections={codexConnections}
              onChange={handleAgentChange}
            />

            <div>
              <Button type="primary" loading={saving} onClick={persist}>保存编排配置</Button>
            </div>
          </Space>
        </div>

        <Modal
          title="AI 生成 Worker"
          open={workerGenerator.open}
          onCancel={() => setWorkerGenerator({ open: false, goal: '', reason: '' })}
          onOk={generateWorker}
          confirmLoading={generatingWorker}
          okText="生成 Worker"
        >
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            <Text type="secondary">
              描述你想新增的一组 Worker 角色，例如“做一个宠物产品页面，需要产品、前端和测试协作”。
            </Text>
            <Input.TextArea
              rows={5}
              value={workerGenerator.goal}
              onChange={(event) => setWorkerGenerator((prev) => ({ ...prev, goal: event.target.value }))}
              placeholder="例如：做一个宠物产品页面，需要拆出产品经理、前端研发、测试 3 个 Worker。"
            />
          </Space>
        </Modal>
      </Space>
    </div>
  )
}
