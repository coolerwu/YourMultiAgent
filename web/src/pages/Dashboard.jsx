/**
 * pages/Dashboard.jsx
 *
 * 主页面：左侧 Agent 图列表 + 右侧 设计器/运行器/Worker 状态 标签页。
 */

import { PlusOutlined, RobotOutlined } from '@ant-design/icons'
import { Button, Layout, List, Popconfirm, Tabs, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import AgentDesigner from '../components/AgentDesigner'
import AgentRunner from '../components/AgentRunner'
import WorkerStatus from '../components/WorkerStatus'
import { graphApi } from '../utils/graphApi'

const { Sider, Content } = Layout
const { Title, Text } = Typography

export default function Dashboard() {
  const [graphs, setGraphs] = useState([])
  const [selected, setSelected] = useState(null)  // 当前选中的 GraphVO
  const [creating, setCreating] = useState(false)  // 是否在新建模式

  const loadGraphs = () =>
    graphApi.list().then(setGraphs).catch((e) => message.error(e.message))

  useEffect(() => { loadGraphs() }, [])

  const handleDelete = async (id) => {
    try {
      await graphApi.delete(id)
      message.success('已删除')
      if (selected?.id === id) { setSelected(null); setCreating(false) }
      loadGraphs()
    } catch (e) {
      message.error(e.message)
    }
  }

  const handleSaved = (savedGraph) => {
    setSelected(savedGraph)
    setCreating(false)
    loadGraphs()
  }

  const tabItems = [
    {
      key: 'designer',
      label: '配置',
      children: (
        <AgentDesigner
          graph={creating ? null : selected}
          onSaved={handleSaved}
        />
      ),
    },
    {
      key: 'runner',
      label: '运行',
      children: (
        <div style={{ padding: 16, height: 'calc(100vh - 160px)', display: 'flex', flexDirection: 'column' }}>
          {selected
            ? <AgentRunner graphId={selected.id} />
            : <Text type="secondary">请先从左侧选择一个 Agent 图</Text>
          }
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
    <Layout style={{ minHeight: '100vh' }}>
      <Sider width={240} theme="light" style={{ borderRight: '1px solid #f0f0f0', padding: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <Title level={5} style={{ margin: 0 }}>
            <RobotOutlined /> Agent 图
          </Title>
          <Button
            icon={<PlusOutlined />}
            size="small"
            type="primary"
            onClick={() => { setCreating(true); setSelected(null) }}
          />
        </div>

        <List
          dataSource={graphs}
          renderItem={(g) => (
            <List.Item
              style={{
                cursor: 'pointer',
                padding: '6px 8px',
                borderRadius: 6,
                background: selected?.id === g.id ? '#e6f4ff' : 'transparent',
              }}
              onClick={() => { setSelected(g); setCreating(false) }}
              actions={[
                <Popconfirm
                  key="del"
                  title="确认删除？"
                  onConfirm={(e) => { e.stopPropagation(); handleDelete(g.id) }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <Button size="small" danger type="link">删除</Button>
                </Popconfirm>,
              ]}
            >
              <Text ellipsis style={{ maxWidth: 130 }}>{g.name}</Text>
            </List.Item>
          )}
          locale={{ emptyText: '暂无 Agent 图' }}
        />
      </Sider>

      <Content>
        <Tabs
          items={tabItems}
          style={{ padding: '0 16px' }}
          defaultActiveKey={creating ? 'designer' : 'runner'}
          activeKey={creating ? 'designer' : undefined}
        />
      </Content>
    </Layout>
  )
}
