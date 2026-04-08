/**
 * pages/Dashboard.jsx
 *
 * 主页面布局：
 * - 左侧加载全部 Workspace
 * - 每个 Workspace 只展示一套单编排配置
 * - 右侧标签页：配置 / 运行 / Worker
 */

import {
  ApiOutlined,
  DeleteOutlined,
  FolderOpenOutlined,
  PlusOutlined,
  RobotOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { Button, Layout, Popconfirm, Skeleton, Space, Tabs, Tooltip, Typography, message } from 'antd'
import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { workspaceApi } from '../utils/workspaceApi'

const { Sider, Content } = Layout
const { Text } = Typography
const ProviderManager = lazy(() => import('../components/ProviderManager'))
const SystemSettings = lazy(() => import('../components/SystemSettings'))
const WorkerStatus = lazy(() => import('../components/WorkerStatus'))
const WorkspaceManager = lazy(() => import('../components/WorkspaceManager'))
const WorkspaceOrchestrationEditor = lazy(() => import('../components/WorkspaceOrchestrationEditor'))
const WorkspaceRunView = lazy(() => import('../components/WorkspaceRunView'))

function TabFallback() {
  return (
    <div style={{ padding: 16 }}>
      <Skeleton active paragraph={{ rows: 6 }} />
    </div>
  )
}

function ModalFallback() {
  return null
}

function WorkspaceCard({ workspace, active, deleting, onSelect, onEditWorkspace, onDeleteWorkspace }) {
  return (
    <div
      onClick={() => onSelect(workspace)}
      style={{
        background: active ? '#eff8ff' : '#fff',
        border: active ? '1px solid #b2ddff' : '1px solid #eceff3',
        borderRadius: 14,
        marginBottom: 10,
        padding: '12px 12px 12px 10px',
        boxShadow: '0 1px 2px rgba(16,24,40,0.04)',
        cursor: 'pointer',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 10,
            background: '#eef4ff',
            color: '#1677ff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <FolderOpenOutlined style={{ fontSize: 18 }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 16, color: '#101828', lineHeight: 1.2 }}>
            {workspace.name}
          </div>
          <div style={{ fontSize: 11, color: '#667085', marginTop: 4 }}>
            目录：{workspace.dir_name || 'workspace'}
          </div>
          <div style={{ fontSize: 11, color: '#98a2b3', marginTop: 2, wordBreak: 'break-all' }}>
            {workspace.work_dir}
          </div>
          <div style={{ marginTop: 6 }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                height: 22,
                padding: '0 8px',
                borderRadius: 999,
                background: '#f2f4f7',
                color: '#667085',
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              单编排配置
            </span>
          </div>
        </div>
        <Space size={2} onClick={(e) => e.stopPropagation()}>
          <Tooltip title="编辑 Workspace">
            <Button size="small" type="text" icon={<SettingOutlined />} onClick={() => onEditWorkspace(workspace)} />
          </Tooltip>
          <Popconfirm
            title="删除 Workspace"
            description={`确认删除「${workspace.name}」吗？`}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true, loading: deleting }}
            onConfirm={() => onDeleteWorkspace(workspace)}
          >
            <Tooltip title="删除 Workspace">
              <Button size="small" type="text" danger loading={deleting} icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      </div>
    </div>
  )
}

function NavCard({ icon, title, subtitle, active, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        background: active ? '#eff8ff' : '#fff',
        border: active ? '1px solid #b2ddff' : '1px solid #eceff3',
        borderRadius: 14,
        marginBottom: 10,
        padding: '12px 12px 12px 10px',
        boxShadow: '0 1px 2px rgba(16,24,40,0.04)',
        cursor: 'pointer',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 10,
            background: '#eef4ff',
            color: '#1677ff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          {icon}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 16, color: '#101828', lineHeight: 1.2 }}>
            {title}
          </div>
          <div style={{ fontSize: 12, color: '#667085', marginTop: 4 }}>
            {subtitle}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [workspaces, setWorkspaces] = useState([])
  const [activeWorkspace, setActiveWorkspace] = useState(null)
  const [activeTab, setActiveTab] = useState('designer')
  const [activePanel, setActivePanel] = useState('workspace')
  const [wsModalOpen, setWsModalOpen] = useState(false)
  const [editingWorkspace, setEditingWorkspace] = useState(null)
  const [orchestrationVersion, setOrchestrationVersion] = useState(0)
  const [deletingWorkspaceId, setDeletingWorkspaceId] = useState('')

  const loadWorkspaces = async ({ preservePanel = false } = {}) => {
    try {
      const result = await workspaceApi.list()
      setWorkspaces(result)
      const refreshed = activeWorkspace
        ? result.find((item) => item.id === activeWorkspace.id) ?? null
        : null
      const nextActive = refreshed ?? result[0] ?? null
      setActiveWorkspace(nextActive)
      if (nextActive && !preservePanel) {
        setActivePanel('workspace')
      }
    } catch (e) {
      message.error(e.message)
    }
  }

  useEffect(() => {
    loadWorkspaces()
  }, [])

  const handleWorkspaceSaved = (workspace) => {
    loadWorkspaces()
    setActiveWorkspace((prev) => (prev?.id === workspace.id ? workspace : prev))
  }

  const handleWorkspaceDelete = async (workspace) => {
    try {
      setDeletingWorkspaceId(workspace.id)
      await workspaceApi.delete(workspace.id)
      await loadWorkspaces()
      message.success(`已删除 Workspace「${workspace.name}」`)
    } catch (e) {
      message.error(e.message)
    } finally {
      setDeletingWorkspaceId('')
    }
  }

  const tabItems = useMemo(() => ([
    {
      key: 'designer',
      label: '配置',
      children: (
        <Suspense fallback={<TabFallback />}>
          <WorkspaceOrchestrationEditor
            key={`${activeWorkspace?.id ?? 'none'}-${orchestrationVersion}`}
            workspace={activeWorkspace}
            onSaved={() => setOrchestrationVersion((prev) => prev + 1)}
          />
        </Suspense>
      ),
    },
    {
      key: 'runner',
      label: '运行',
      children: (
        <Suspense fallback={<TabFallback />}>
          <div style={{ height: 'calc(100vh - 108px)', display: 'flex', flexDirection: 'column' }}>
            <WorkspaceRunView key={`${activeWorkspace?.id ?? 'none'}-${orchestrationVersion}-run`} workspace={activeWorkspace} />
          </div>
        </Suspense>
      ),
    },
    {
      key: 'worker',
      label: 'Worker',
      children: (
        <Suspense fallback={<TabFallback />}>
          <div style={{ padding: 16 }}><WorkerStatus /></div>
        </Suspense>
      ),
    },
  ]), [activeWorkspace, orchestrationVersion])

  return (
    <Layout style={{ minHeight: '100vh', background: '#f8fafc' }}>
      <Sider width={320} theme="light" style={{ borderRight: '1px solid #eaecf0', padding: 16, background: '#fcfcfd' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
            padding: '8px 6px 16px',
            borderBottom: '1px solid #eaecf0',
            marginBottom: 18,
          }}
        >
          <Space size={12}>
            <div
              style={{
                width: 42,
                height: 42,
                borderRadius: 14,
                background: 'linear-gradient(135deg, #eef4ff 0%, #dbeafe 100%)',
                color: '#1677ff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <RobotOutlined style={{ fontSize: 22 }} />
            </div>
            <div>
              <div style={{ fontWeight: 800, fontSize: 18, color: '#101828', lineHeight: 1.1 }}>Agent 智能体</div>
              <div style={{ fontSize: 12, color: '#667085', marginTop: 3 }}>单主控 + 多 Worker</div>
            </div>
          </Space>
          <Tooltip title="新建 Workspace">
            <Button icon={<PlusOutlined />} size="middle" type="text" onClick={() => { setEditingWorkspace(null); setWsModalOpen(true) }} />
          </Tooltip>
        </div>

        <div style={{ marginBottom: 12, padding: '0 4px' }}>
          <Text type="secondary" style={{ fontSize: 11, letterSpacing: '0.08em' }}>WORKSPACES</Text>
        </div>

        <div>
          {workspaces.map((workspace) => (
            <WorkspaceCard
              key={workspace.id}
              workspace={workspace}
              active={activePanel === 'workspace' && activeWorkspace?.id === workspace.id}
              deleting={deletingWorkspaceId === workspace.id}
              onSelect={(ws) => {
                setActiveWorkspace(ws)
                setActivePanel('workspace')
              }}
              onEditWorkspace={(ws) => {
                setEditingWorkspace(ws)
                setWsModalOpen(true)
              }}
              onDeleteWorkspace={handleWorkspaceDelete}
            />
          ))}
        </div>

        <div style={{ margin: '18px 0 12px', padding: '0 4px' }}>
          <Text type="secondary" style={{ fontSize: 11, letterSpacing: '0.08em' }}>PROVIDERS</Text>
        </div>

        <NavCard
          icon={<ApiOutlined style={{ fontSize: 18 }} />}
          title="全局模型连接"
          subtitle="统一管理 API Provider 和 Codex 登录"
          active={activePanel === 'providers'}
          onClick={() => setActivePanel('providers')}
        />

        <div style={{ margin: '18px 0 12px', padding: '0 4px' }}>
          <Text type="secondary" style={{ fontSize: 11, letterSpacing: '0.08em' }}>SYSTEM</Text>
        </div>

        <NavCard
          icon={<SettingOutlined style={{ fontSize: 18 }} />}
          title="系统设置"
          subtitle="执行 Update Now 和查看系统级状态"
          active={activePanel === 'system'}
          onClick={() => setActivePanel('system')}
        />
      </Sider>

      <Content>
        {activePanel === 'providers' ? (
          <Suspense fallback={<TabFallback />}>
            <ProviderManager embedded onSaved={() => loadWorkspaces({ preservePanel: true })} />
          </Suspense>
        ) : activePanel === 'system' ? (
          <Suspense fallback={<TabFallback />}>
            <SystemSettings />
          </Suspense>
        ) : activeWorkspace ? (
          <Tabs
            activeKey={activeTab}
            destroyInactiveTabPane
            items={tabItems}
            onChange={setActiveTab}
            style={{ padding: '0 18px', background: '#fff', minHeight: '100vh' }}
          />
        ) : (
          <div style={{ height: '100%', background: '#fff' }} />
        )}
      </Content>

      <Suspense fallback={<ModalFallback />}>
        <WorkspaceManager
          open={wsModalOpen}
          workspace={editingWorkspace}
          onClose={() => setWsModalOpen(false)}
          onSaved={handleWorkspaceSaved}
        />
      </Suspense>
    </Layout>
  )
}
