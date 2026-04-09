import { ArrowDownOutlined, ArrowUpOutlined, DeleteOutlined } from '@ant-design/icons'
import { Button, Card, Space, Tag, Typography } from 'antd'

const { Text } = Typography

export default function AgentSummaryCard({
  title,
  subtitle,
  description,
  tools,
  active = false,
  onClick,
  extra,
}) {
  return (
    <Card
      size="small"
      hoverable
      onClick={onClick}
      style={{
        cursor: onClick ? 'pointer' : 'default',
        borderColor: active ? '#1677ff' : undefined,
        boxShadow: active ? '0 0 0 2px rgba(22,119,255,0.12)' : undefined,
      }}
      title={title}
      extra={extra}
    >
      <Space direction="vertical" size={4} style={{ width: '100%' }}>
        {subtitle ? <Text type="secondary">{subtitle}</Text> : null}
        {description ? <Text type="secondary">{description}</Text> : null}
        {tools?.length ? (
          <div>
            {tools.map((tool) => <Tag key={tool}>{tool}</Tag>)}
          </div>
        ) : null}
      </Space>
    </Card>
  )
}

export function WorkerCardActions({
  index,
  total,
  onMoveUp,
  onMoveDown,
  onDelete,
}) {
  return (
    <Space onClick={(event) => event.stopPropagation()}>
      <Button size="small" icon={<ArrowUpOutlined />} disabled={index === 0} onClick={onMoveUp} />
      <Button size="small" icon={<ArrowDownOutlined />} disabled={index === total - 1} onClick={onMoveDown} />
      <Button size="small" danger icon={<DeleteOutlined />} onClick={onDelete} />
    </Space>
  )
}
