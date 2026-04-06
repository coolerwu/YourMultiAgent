/**
 * components/WorkerStatus.jsx
 *
 * 展示内置 Local Worker 的已注册 capability 列表。
 */

import { CheckCircleOutlined } from '@ant-design/icons'
import { Card, Table, Tag, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { workerApi } from '../utils/graphApi'

const { Text } = Typography

export default function WorkerStatus() {
  const [caps, setCaps] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    workerApi.listCapabilities()
      .then(setCaps)
      .finally(() => setLoading(false))
  }, [])

  const columns = [
    {
      title: 'Capability',
      dataIndex: 'name',
      render: (name) => <Text code>{name}</Text>,
    },
    { title: '描述', dataIndex: 'description' },
    {
      title: '参数',
      dataIndex: 'parameters',
      render: (params) =>
        params.map((p) => (
          <Tag key={p.name} color={p.required ? 'volcano' : 'default'}>
            {p.name}: {p.type}
          </Tag>
        )),
    },
    {
      title: 'Worker',
      dataIndex: 'worker_id',
      render: (id) => (
        <Tag icon={<CheckCircleOutlined />} color="success">{id}</Tag>
      ),
    },
  ]

  return (
    <Card title="内置 Worker Capabilities" size="small" loading={loading}>
      <Table
        dataSource={caps}
        columns={columns}
        rowKey="name"
        size="small"
        pagination={false}
      />
    </Card>
  )
}
