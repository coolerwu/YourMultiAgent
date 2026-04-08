/**
 * components/WorkspaceManager.jsx
 *
 * Workspace 管理弹窗：只维护 Workspace 自身信息。
 */

import { Form, Input, Modal, message } from 'antd'
import { useEffect, useState } from 'react'
import { workspaceApi } from '../utils/workspaceApi'

function sanitizeWorkspaceName(name) {
  const safe = (name || '')
    .trim()
    .replace(/[^a-zA-Z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return safe || 'workspace'
}

export default function WorkspaceManager({ open, workspace, mode = 'workspace', onClose, onSaved }) {
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const isEdit = !!workspace
  const isChat = (workspace?.kind || mode) === 'chat'
  const currentName = Form.useWatch('name', form)
  const currentDirName = Form.useWatch('dir_name', form)
  const currentWorkDir = Form.useWatch('work_dir', form)
  const previewDirName = sanitizeWorkspaceName(currentDirName || workspace?.dir_name || currentName)

  useEffect(() => {
    if (!open) return
    form.setFieldsValue(
      workspace ?? {
        name: '',
        dir_name: '',
        work_dir: '',
        kind: mode,
      }
    )
  }, [open, workspace, form, mode])

  const handleOk = async () => {
    let vals
    try {
      vals = await form.validateFields()
    } catch {
      return
    }

    setSaving(true)
    try {
      const payload = workspace
        ? { ...workspace, ...vals }
        : { ...vals, kind: mode }
      const saved = isEdit
        ? await workspaceApi.update(workspace.id, payload)
        : await workspaceApi.create(payload)
      message.success(isEdit ? '已更新' : isChat ? '单聊目录已创建' : '创建成功')
      onSaved?.(saved)
      onClose?.()
    } catch (e) {
      message.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      title={isEdit ? (isChat ? '编辑单聊目录' : '编辑 Workspace') : (isChat ? '新建单聊目录' : '新建 Workspace')}
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={saving}
      width={560}
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item name="name" label={isChat ? '单聊名称' : '名称'} rules={[{ required: true, message: '请输入名称' }]}>
          <Input placeholder={isChat ? '例如：PetTrace' : '例如：我的项目'} />
        </Form.Item>

        <Form.Item
          name="dir_name"
          label="文件夹名"
          rules={[{ required: isChat, message: '请输入文件夹名' }]}
          extra={isChat ? '单聊的会话历史、compact 摘要和 memory 都会保存在这个目录中。' : '选填。留空时默认由名称自动生成。'}
        >
          <Input placeholder={isChat ? '例如：pettrace' : '例如：my-workspace'} />
        </Form.Item>

        <Form.Item
          name="work_dir"
          label="根目录（work_dir）"
          extra={`选填。留空时默认使用 DATA_DIR/workspaces/${previewDirName}；开发模式通常是当前项目 data 目录。`}
        >
          <Input placeholder="留空使用默认目录，例如：~/projects/my-workspace" />
        </Form.Item>

        <div
          style={{
            marginTop: 6,
            padding: '12px 14px',
            borderRadius: 12,
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
          }}
        >
          <div style={{ fontSize: 12, color: '#475467', marginBottom: 6 }}>目录映射</div>
          <div style={{ fontSize: 13, color: '#101828', fontWeight: 600 }}>
            目录名：{previewDirName}
          </div>
          <div style={{ fontSize: 12, color: '#667085', marginTop: 4, wordBreak: 'break-all' }}>
            实际目录：{currentWorkDir?.trim() || `DATA_DIR/workspaces/${previewDirName}`}
          </div>
        </div>
      </Form>
    </Modal>
  )
}
