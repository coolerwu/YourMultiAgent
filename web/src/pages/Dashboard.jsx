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
  FolderOpenOutlined,
  PlusOutlined,
  RobotOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { Button, Layout, Space, Tabs, Tooltip, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import ProviderManager from '../components/ProviderManager'
import WorkerStatus from '../components/WorkerStatus'
import WorkspaceManager from '../components/WorkspaceManager'
import WorkspaceOrchestrationEditor from '../components/WorkspaceOrchestrationEditor'
import WorkspaceRunView from '../components/WorkspaceRunView'
import { workspaceApi } from '../utils/workspaceApi'

const { Sider, Content } = Layout
const { Text } = Typography

function WorkspaceCard({ workspace, active, onSelect, onEditWorkspace, onEditProviders }) {
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
          <Tooltip title="Provider 配置">
            <Button size="small" type="text" icon={<ApiOutlined />} onClick={() => onEditProviders(workspace)} />
          </Tooltip>
          <Tooltip title="编辑 Workspace">
            <Button size="small" type="text" icon={<SettingOutlined />} onClick={() => onEditWorkspace(workspace)} />
          </Tooltip>
        </Space>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [workspaces, setWorkspaces] = useState([])
  const [activeWorkspace, setActiveWorkspace] = useState(null)
  const [wsModalOpen, setWsModalOpen] = useState(false)
  const [editingWorkspace, setEditingWorkspace] = useState(null)
  const [providerModalOpen, setProviderModalOpen] = useState(false)
  const [providerWorkspace, setProviderWorkspace] = useState(null)
  const [orchestrationVersion, setOrchestrationVersion] = useState(0)

  const loadWorkspaces = async () => {
    try {
      const result = await workspaceApi.list()
      setWorkspaces(result)
      if (!activeWorkspace && result.length > 0) {
        setActiveWorkspace(result[0])
      } else if (activeWorkspace) {
        const refreshed = result.find((item) => item.id === activeWorkspace.id) ?? null
        setActiveWorkspace(refreshed)
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

  const tabItems = [
    {
      key: 'designer',
      label: '配置',
      children: (
        <WorkspaceOrchestrationEditor
          key={`${activeWorkspace?.id ?? 'none'}-${orchestrationVersion}`}
          workspace={activeWorkspace}
          onSaved={() => setOrchestrationVersion((prev) => prev + 1)}
        />
      ),
    },
    {
      key: 'runner',
      label: '运行',
      children: (
        <div style={{ height: 'calc(100vh - 108px)', display: 'flex', flexDirection: 'column' }}>
          <WorkspaceRunView key={`${activeWorkspace?.id ?? 'none'}-${orchestrationVersion}-run`} workspace={activeWorkspace} />
        </div>
      ),
    },
    {
      key: 'worker',
      label: 'Worker',
      children: <div style={{ padding: 16 }}><WorkerStatus /></div>,
    },
  ]

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
              active={activeWorkspace?.id === workspace.id}
              onSelect={setActiveWorkspace}
              onEditWorkspace={(ws) => {
                setEditingWorkspace(ws)
                setWsModalOpen(true)
              }}
              onEditProviders={(ws) => {
                setProviderWorkspace(ws)
                setProviderModalOpen(true)
              }}
            />
          ))}
        </div>
      </Sider>

      <Content>
        {activeWorkspace ? (
          <Tabs items={tabItems} style={{ padding: '0 18px', background: '#fff', minHeight: '100vh' }} />
        ) : (
          <div style={{ height: '100%', background: '#fff' }} />
        )}
      </Content>

      <WorkspaceManager
        open={wsModalOpen}
        workspace={editingWorkspace}
        onClose={() => setWsModalOpen(false)}
        onSaved={handleWorkspaceSaved}
      />
      <ProviderManager
        open={providerModalOpen}
        workspace={providerWorkspace}
        onClose={() => setProviderModalOpen(false)}
        onSaved={handleWorkspaceSaved}
      />
    </Layout>
  )
}
