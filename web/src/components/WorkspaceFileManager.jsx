/**
 * components/WorkspaceFileManager.jsx
 *
 * Workspace 文件管理器：浏览、删除文件/文件夹
 * 路径安全由后端保证，前端只做展示和交互
 */

import { useEffect, useState, useCallback } from 'react'
import {
  Breadcrumb,
  Button,
  Card,
  Empty,
  List,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Typography,
  message,
} from 'antd'
import {
  DeleteOutlined,
  FileOutlined,
  FolderOutlined,
  HomeOutlined,
  ReloadOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons'
import { workspaceApi } from '../utils/workspaceApi'

const { Text } = Typography

function formatSize(size) {
  if (size === null || size === undefined) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export default function WorkspaceFileManager({ workspace }) {
  const [loading, setLoading] = useState(false)
  const [currentPath, setCurrentPath] = useState('.')
  const [entries, setEntries] = useState([]
)
  const [selectedEntry, setSelectedEntry] = useState(null)
  const [deleteModalVisible, setDeleteModalVisible] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [recursiveDelete, setRecursiveDelete] = useState(false)

  const loadFiles = useCallback(async () => {
    if (!workspace?.id) return
    setLoading(true)
    try {
      const result = await workspaceApi.listFiles(workspace.id, currentPath)
      if (result.entries) {
        // 目录排在前面，文件排在后面，各自按名称排序
        const sorted = result.entries.sort((a, b) => {
          if (a.is_dir === b.is_dir) {
            return a.name.localeCompare(b.name)
          }
          return a.is_dir ? -1 : 1
        })
        setEntries(sorted)
      } else {
        setEntries([])
      }
    } catch (e) {
      message.error(e.message || '加载文件列表失败')
      setEntries([])
    } finally {
      setLoading(false)
    }
  }, [workspace?.id, currentPath])

  useEffect(() => {
    loadFiles()
  }, [loadFiles])

  const handleEnterDir = (dirName) => {
    const newPath = currentPath === '.' ? dirName : `${currentPath}/${dirName}`
    setCurrentPath(newPath)
  }

  const handleGoUp = () => {
    if (currentPath === '.') return
    const parts = currentPath.split('/')
    parts.pop()
    setCurrentPath(parts.length === 0 ? '.' : parts.join('/'))
  }

  const handleGoHome = () => {
    setCurrentPath('.')
  }

  const handleDelete = async () => {
    if (!selectedEntry) return
    setDeleteLoading(true)
    try {
      const path = currentPath === '.' ? selectedEntry.name : `${currentPath}/${selectedEntry.name}`
      await workspaceApi.deleteFile(workspace.id, path, recursiveDelete)
      message.success(`已删除 ${selectedEntry.is_dir ? '目录' : '文件'}「${selectedEntry.name}」`)
      setDeleteModalVisible(false)
      setSelectedEntry(null)
      setRecursiveDelete(false)
      loadFiles()
    } catch (e) {
      message.error(e.message || '删除失败')
    } finally {
      setDeleteLoading(false)
    }
  }

  const showDeleteConfirm = (entry) => {
    setSelectedEntry(entry)
    setRecursiveDelete(false)
    setDeleteModalVisible(true)
  }

  const renderBreadcrumb = () => {
    const items = [{ title: <HomeOutlined />, onClick: handleGoHome }]
    if (currentPath !== '.') {
      const parts = currentPath.split('/')
      parts.forEach((part, index) => {
        const path = parts.slice(0, index + 1).join('/')
        items.push({
          title: part,
          onClick: () => setCurrentPath(path),
        })
      })
    }
    return <Breadcrumb items={items} style={{ marginBottom: 16 }} />
  }

  return (
    <Card
      title={
        <Space>
          <span>文件管理</span>
          <Text type="secondary" style={{ fontSize: 12, fontWeight: 'normal' }}>
            {workspace?.work_dir || ''}
          </Text>
        </Space>
      }
      extra={
        <Space>
          <Button
            icon={<ArrowLeftOutlined />}
            disabled={currentPath === '.' || loading}
            onClick={handleGoUp}
          >
            上级
          </Button>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={loadFiles}>
            刷新
          </Button>
        </Space>
      }
      bodyStyle={{ padding: 16, minHeight: 400 }}
    >
      {renderBreadcrumb()}

      <Spin spinning={loading}>
        {entries.length === 0 ? (
          <Empty description="空目录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <List
            bordered
            dataSource={entries}
            renderItem={(item) => (
              <List.Item
                actions={[
                  <Popconfirm
                    key="delete"
                    title={`确认删除${item.is_dir ? '目录' : '文件'}？`}
                    description={`${item.name}${item.is_dir ? '（仅空目录可直接删除）' : ''}`}
                    okText="删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                    onConfirm={() => showDeleteConfirm(item)}
                  >
                    <Button size="small" danger icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  avatar={
                    item.is_dir ? (
                      <FolderOutlined style={{ fontSize: 20, color: '#faad14' }} />
                    ) : (
                      <FileOutlined style={{ fontSize: 20, color: '#1890ff' }} />
                    )
                  }
                  title={
                    item.is_dir ? (
                      <Button
                        type="link"
                        style={{ padding: 0, fontWeight: 500 }}
                        onClick={() => handleEnterDir(item.name)}
                      >
                        {item.name}
                      </Button>
                    ) : (
                      <Text>{item.name}</Text>
                    )
                  }
                  description={item.is_dir ? '目录' : `文件 · ${formatSize(item.size)}`}
                />
              </List.Item>
            )}
          />
        )}
      </Spin>

      {/* 删除确认弹窗 - 针对非空目录时显示递归选项 */}
      <Modal
        title={`确认删除${selectedEntry?.is_dir ? '目录' : '文件'}`}
        open={deleteModalVisible}
        onCancel={() => {
          setDeleteModalVisible(false)
          setSelectedEntry(null)
          setRecursiveDelete(false)
        }}
        footer={[
          <Button
            key="cancel"
            onClick={() => {
              setDeleteModalVisible(false)
              setSelectedEntry(null)
              setRecursiveDelete(false)
            }}
          >
            取消
          </Button>,
          <Button
            key="delete"
            danger
            loading={deleteLoading}
            onClick={handleDelete}
          >
            {selectedEntry?.is_dir && recursiveDelete ? '强制删除' : '确认删除'}
          </Button>,
        ]}
      >
        <p>
          确定要删除
          <strong>「{selectedEntry?.name}」</strong>
          吗？
        </p>
        {selectedEntry?.is_dir && (
          <div style={{ marginTop: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={recursiveDelete}
                onChange={(e) => setRecursiveDelete(e.target.checked)}
              />
              <span>强制删除非空目录（包含所有子文件和子目录）</span>
            </label>
          </div>
        )}
        <Text type="secondary" style={{ display: 'block', marginTop: 16, fontSize: 12 }}>
          此操作不可恢复，请谨慎操作。
        </Text>
      </Modal>
    </Card>
  )
}
