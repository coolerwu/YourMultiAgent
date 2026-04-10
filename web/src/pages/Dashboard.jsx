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
  CaretRightOutlined,
  CommentOutlined,
  DeleteOutlined,
  EditOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  MenuFoldOutlined,
  MenuOutlined,
  MenuUnfoldOutlined,
  PlusOutlined,
  RobotOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { Button, Collapse, Drawer, Grid, Layout, Popconfirm, Skeleton, Space, Tabs, Tooltip, Typography, message } from 'antd'
import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { workspaceApi } from '../utils/workspaceApi'
import './Dashboard.css'

const { Sider, Content } = Layout
const { Text } = Typography
const ProviderManager = lazy(() => import('../components/ProviderManager'))
const AppLogViewer = lazy(() => import('../components/AppLogViewer'))
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

function buildTabItems(workspace, orchestrationVersion, onOrchestrationSaved) {
  const isChat = workspace?.kind === 'chat'
  return [
    {
      key: 'designer',
      label: '配置',
      children: (
        <Suspense fallback={<TabFallback />}>
          <div className="dashboard-tab-pane dashboard-tab-pane-scroll">
            <WorkspaceOrchestrationEditor
              key={`${workspace?.id ?? 'none'}-${orchestrationVersion}`}
              workspace={workspace}
              onSaved={onOrchestrationSaved}
            />
          </div>
        </Suspense>
      ),
    },
    {
      key: 'runner',
      label: '运行',
      children: (
        <Suspense fallback={<TabFallback />}>
          <div className="dashboard-tab-pane dashboard-tab-pane-flex">
            <WorkspaceRunView key={`${workspace?.id ?? 'none'}-${orchestrationVersion}-run`} workspace={workspace} />
          </div>
        </Suspense>
      ),
    },
    ...(!isChat ? [{
      key: 'worker',
      label: 'Worker',
      children: (
        <Suspense fallback={<TabFallback />}>
          <div className="dashboard-tab-pane dashboard-tab-pane-scroll" style={{ padding: 16 }}><WorkerStatus /></div>
        </Suspense>
      ),
    }] : []),
  ]
}

// 紧凑列表项（树形导航风格）
function WorkspaceListItem({ workspace, active, deleting, onSelect, onEditWorkspace, onDeleteWorkspace }) {
  const isChat = workspace.kind === 'chat'
  return (
    <div
      onClick={() => onSelect(workspace)}
      className={`dashboard-list-item ${active ? 'dashboard-list-item-active' : ''}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '8px 12px',
        margin: '2px 8px',
        borderRadius: 6,
        cursor: 'pointer',
        transition: 'all 0.2s',
        borderLeft: active ? '3px solid #1677ff' : '3px solid transparent',
        background: active ? '#e6f4ff' : 'transparent',
      }}
    >
      {isChat
        ? <CommentOutlined style={{ fontSize: 14, color: '#1677ff', flexShrink: 0 }} />
        : <FolderOpenOutlined style={{ fontSize: 14, color: '#52c41a', flexShrink: 0 }} />}
      <div style={{ flex: 1, minWidth: 0, overflow: 'hidden' }}>
        <div style={{
          fontWeight: active ? 600 : 500,
          fontSize: 13,
          color: active ? '#1677ff' : '#1f2937',
          lineHeight: 1.3,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>
          {workspace.name}
        </div>
        <div style={{
          fontSize: 11,
          color: '#6b7280',
          marginTop: 1,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>
          {workspace.dir_name || 'workspace'}
        </div>
      </div>
      <Space size={0} onClick={(e) => e.stopPropagation()} style={{ opacity: 0, transition: 'opacity 0.2s' }} className="workspace-actions">
        <Tooltip title="编辑">
          <Button size="small" type="text" icon={<EditOutlined style={{ fontSize: 12 }} />} onClick={() => onEditWorkspace(workspace)} />
        </Tooltip>
        <Popconfirm
          title="删除 Workspace"
          description={`确认删除「${workspace.name}」吗？`}
          okText="删除"
          cancelText="取消"
          okButtonProps={{ danger: true, loading: deleting }}
          onConfirm={() => onDeleteWorkspace(workspace)}
        >
          <Tooltip title="删除">
            <Button size="small" type="text" danger loading={deleting} icon={<DeleteOutlined style={{ fontSize: 12 }} />} />
          </Tooltip>
        </Popconfirm>
      </Space>
    </div>
  )
}

// 简洁的导航列表项
function NavListItem({ icon, title, active, onClick }) {
  return (
    <div
      onClick={onClick}
      className={`dashboard-list-item ${active ? 'dashboard-list-item-active' : ''}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '10px 12px',
        margin: '2px 8px',
        borderRadius: 6,
        cursor: 'pointer',
        transition: 'all 0.2s',
        borderLeft: active ? '3px solid #1677ff' : '3px solid transparent',
        background: active ? '#e6f4ff' : 'transparent',
      }}
    >
      <span style={{ fontSize: 14, color: active ? '#1677ff' : '#6b7280', flexShrink: 0 }}>
        {icon}
      </span>
      <span style={{
        fontWeight: active ? 600 : 500,
        fontSize: 13,
        color: active ? '#1677ff' : '#374151',
        lineHeight: 1.3,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}>
        {title}
      </span>
    </div>
  )
}

function SidebarIconButton({ active, icon, tooltip, onClick }) {
  return (
    <Tooltip placement="right" title={tooltip}>
      <Button
        type="text"
        aria-label={tooltip}
        onClick={onClick}
        className={`dashboard-icon-button ${active ? 'dashboard-icon-button-active' : ''}`}
        icon={icon}
      />
    </Tooltip>
  )
}

function pickDefaultWorkspace(items) {
  return items.find((item) => item.kind === 'chat') ?? items[0] ?? null
}

export default function Dashboard() {
  const storageKey = 'dashboard-sidebar-collapsed'
  const screens = Grid.useBreakpoint()
  const isMobile = !screens.md
  const [workspaces, setWorkspaces] = useState([])
  const [activeWorkspace, setActiveWorkspace] = useState(null)
  const [activeTab, setActiveTab] = useState('runner')
  const [activePanel, setActivePanel] = useState('workspace')
  const [wsModalOpen, setWsModalOpen] = useState(false)
  const [editingWorkspace, setEditingWorkspace] = useState(null)
  const [orchestrationVersion, setOrchestrationVersion] = useState(0)
  const [deletingWorkspaceId, setDeletingWorkspaceId] = useState('')
  const [managerMode, setManagerMode] = useState('workspace')
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.localStorage.getItem(storageKey) === '1'
  })

  const loadWorkspaces = async ({ preservePanel = false } = {}) => {
    try {
      const result = await workspaceApi.list()
      setWorkspaces(result)
      const refreshed = activeWorkspace
        ? result.find((item) => item.id === activeWorkspace.id) ?? null
        : null
      const nextActive = refreshed ?? pickDefaultWorkspace(result)
      setActiveWorkspace(nextActive)
      if (nextActive && !preservePanel) {
        setActivePanel(nextActive.kind === 'chat' ? 'chat' : 'workspace')
        setActiveTab('runner')
      }
    } catch (e) {
      message.error(e.message)
    }
  }

  useEffect(() => {
    loadWorkspaces()
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(storageKey, sidebarCollapsed ? '1' : '0')
  }, [sidebarCollapsed])

  const handleWorkspaceSaved = (workspace) => {
    loadWorkspaces()
    setActiveWorkspace(workspace)
    setActivePanel(workspace.kind === 'chat' ? 'chat' : 'workspace')
    setActiveTab('runner')
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

  const tabItems = useMemo(
    () => buildTabItems(activeWorkspace, orchestrationVersion, () => setOrchestrationVersion((prev) => prev + 1)),
    [activeWorkspace, orchestrationVersion],
  )

  const chatSpaces = useMemo(() => workspaces.filter((workspace) => workspace.kind === 'chat'), [workspaces])
  const orchestrationSpaces = useMemo(() => workspaces.filter((workspace) => workspace.kind !== 'chat'), [workspaces])

  const renderCollapsedWorkspaceGroup = (items, section, kind) => (
    <div className="dashboard-icon-group">
      {items.map((workspace) => (
        <SidebarIconButton
          key={workspace.id}
          tooltip={workspace.name}
          active={activePanel === kind && activeWorkspace?.id === workspace.id}
          icon={kind === 'chat' ? <CommentOutlined style={{ fontSize: 18 }} /> : <FolderOpenOutlined style={{ fontSize: 18 }} />}
          onClick={() => {
            setActiveWorkspace(workspace)
            setActivePanel(kind)
            setActiveTab('runner')
            setMobileNavOpen(false)
          }}
        />
      ))}
      <SidebarIconButton
        tooltip={section}
        active={false}
        icon={<PlusOutlined style={{ fontSize: 18 }} />}
        onClick={() => {
          setEditingWorkspace(null)
          setManagerMode(kind)
          setWsModalOpen(true)
          setMobileNavOpen(false)
        }}
      />
    </div>
  )

  const renderSidebar = (collapsed = false) => (
    <>
      <div className={`dashboard-brand ${collapsed ? 'dashboard-brand-collapsed' : ''}`}>
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
          {!collapsed && (
            <div>
              <div style={{ fontWeight: 800, fontSize: 18, color: '#101828', lineHeight: 1.1 }}>Agent 智能体</div>
              <div style={{ fontSize: 12, color: '#667085', marginTop: 3 }}>单主控 + 多 Worker</div>
            </div>
          )}
        </Space>
        {!isMobile && (
          <Tooltip title={collapsed ? '展开导航' : '折叠导航'}>
            <Button
              type="text"
              aria-label={collapsed ? '展开导航' : '折叠导航'}
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setSidebarCollapsed((prev) => !prev)}
            />
          </Tooltip>
        )}
      </div>

      {collapsed ? (
        <>
          {renderCollapsedWorkspaceGroup(chatSpaces, '新建单聊目录', 'chat')}
          {renderCollapsedWorkspaceGroup(orchestrationSpaces, '新建 Workspace', 'workspace')}
          <div className="dashboard-icon-group">
            <SidebarIconButton
              tooltip="全局模型连接"
              active={activePanel === 'providers'}
              icon={<ApiOutlined style={{ fontSize: 18 }} />}
              onClick={() => {
                setActivePanel('providers')
                setMobileNavOpen(false)
              }}
            />
            <SidebarIconButton
              tooltip="系统设置"
              active={activePanel === 'system'}
              icon={<SettingOutlined style={{ fontSize: 18 }} />}
              onClick={() => {
                setActivePanel('system')
                setMobileNavOpen(false)
              }}
            />
            <SidebarIconButton
              tooltip="应用日志"
              active={activePanel === 'app-log'}
              icon={<FileTextOutlined style={{ fontSize: 18 }} />}
              onClick={() => {
                setActivePanel('app-log')
                setMobileNavOpen(false)
              }}
            />
          </div>
        </>
      ) : (
        <>
          {/* 简洁分组标题 */}
          <div style={{ padding: '12px 12px 4px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em' }}>单聊目录 ({chatSpaces.length})</span>
            <Tooltip title="新建单聊目录">
              <Button icon={<PlusOutlined style={{ fontSize: 12 }} />} size="small" type="text" onClick={() => { setEditingWorkspace(null); setManagerMode('chat'); setWsModalOpen(true) }} />
            </Tooltip>
          </div>
          <div style={{ padding: '2px 0' }}>
            {chatSpaces.map((workspace) => (
              <WorkspaceListItem
                key={workspace.id}
                workspace={workspace}
                active={activePanel === 'chat' && activeWorkspace?.id === workspace.id}
                deleting={deletingWorkspaceId === workspace.id}
                onSelect={(ws) => {
                  setActiveWorkspace(ws)
                  setActivePanel('chat')
                  setActiveTab('runner')
                  setMobileNavOpen(false)
                }}
                onEditWorkspace={(ws) => {
                  setEditingWorkspace(ws)
                  setManagerMode('chat')
                  setWsModalOpen(true)
                  setMobileNavOpen(false)
                }}
                onDeleteWorkspace={handleWorkspaceDelete}
              />
            ))}
          </div>

          <div style={{ padding: '16px 12px 4px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em' }}>工作区 ({orchestrationSpaces.length})</span>
            <Tooltip title="新建 Workspace">
              <Button icon={<PlusOutlined style={{ fontSize: 12 }} />} size="small" type="text" onClick={() => { setEditingWorkspace(null); setManagerMode('workspace'); setWsModalOpen(true) }} />
            </Tooltip>
          </div>
          <div style={{ padding: '2px 0' }}>
            {orchestrationSpaces.map((workspace) => (
              <WorkspaceListItem
                key={workspace.id}
                workspace={workspace}
                active={activePanel === 'workspace' && activeWorkspace?.id === workspace.id}
                deleting={deletingWorkspaceId === workspace.id}
                onSelect={(ws) => {
                  setActiveWorkspace(ws)
                  setActivePanel('workspace')
                  setActiveTab('runner')
                  setMobileNavOpen(false)
                }}
                onEditWorkspace={(ws) => {
                  setEditingWorkspace(ws)
                  setManagerMode('workspace')
                  setWsModalOpen(true)
                  setMobileNavOpen(false)
                }}
                onDeleteWorkspace={handleWorkspaceDelete}
              />
            ))}
          </div>

          {/* 统一的导航菜单 */}
          <div style={{ marginTop: 12 }}>
            <NavListItem
              icon={<ApiOutlined />}
              title="全局模型连接"
              active={activePanel === 'providers'}
              onClick={() => {
                setActivePanel('providers')
                setMobileNavOpen(false)
              }}
            />
            <NavListItem
              icon={<SettingOutlined />}
              title="系统设置"
              active={activePanel === 'system'}
              onClick={() => {
                setActivePanel('system')
                setMobileNavOpen(false)
              }}
            />
            <NavListItem
              icon={<FileTextOutlined />}
              title="应用日志"
              active={activePanel === 'app-log'}
              onClick={() => {
                setActivePanel('app-log')
                setMobileNavOpen(false)
              }}
            />
          </div>
        </>
      )}
    </>
  )

  return (
    <Layout className="dashboard-layout" style={{ overflow: 'hidden' }}>
      <Sider
        width={320}
        collapsed={!isMobile && sidebarCollapsed}
        collapsedWidth={92}
        theme="light"
        className="dashboard-sider"
        style={{ display: isMobile ? 'none' : 'block' }}
      >
        {renderSidebar(sidebarCollapsed)}
      </Sider>

      <Content className="dashboard-content">
        {isMobile && (
          <div className="dashboard-mobile-header">
            <Button type="text" icon={<MenuOutlined />} onClick={() => setMobileNavOpen(true)} />
            <Text strong>{activeWorkspace?.name || '控制台'}</Text>
            <div />
          </div>
        )}
        {activePanel === 'providers' ? (
          <Suspense fallback={<TabFallback />}>
            <ProviderManager embedded onSaved={() => loadWorkspaces({ preservePanel: true })} />
          </Suspense>
        ) : activePanel === 'app-log' ? (
          <Suspense fallback={<TabFallback />}>
            <AppLogViewer />
          </Suspense>
        ) : activePanel === 'system' ? (
          <Suspense fallback={<TabFallback />}>
            <SystemSettings />
          </Suspense>
        ) : activePanel === 'chat' && activeWorkspace ? (
          <Tabs
            activeKey={activeTab}
            destroyInactiveTabPane
            items={tabItems}
            onChange={setActiveTab}
            className="dashboard-tabs"
          />
        ) : activeWorkspace ? (
          <Tabs
            activeKey={activeTab}
            destroyInactiveTabPane
            items={tabItems}
            onChange={setActiveTab}
            className="dashboard-tabs"
          />
        ) : (
          <div style={{ height: '100dvh', background: '#fff' }} />
        )}
      </Content>
      <Drawer
        title="导航"
        placement="left"
        open={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
        width={320}
        styles={{ body: { padding: 16, background: '#fcfcfd' } }}
      >
        {renderSidebar(false)}
      </Drawer>

      <Suspense fallback={<ModalFallback />}>
        <WorkspaceManager
          open={wsModalOpen}
          mode={managerMode}
          workspace={editingWorkspace}
          onClose={() => setWsModalOpen(false)}
          onSaved={handleWorkspaceSaved}
        />
      </Suspense>
    </Layout>
  )
}
