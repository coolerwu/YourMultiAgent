import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import WorkspaceOrchestrationEditor from './WorkspaceOrchestrationEditor'

const { workspaceApiMock, graphApiMock, workerApiMock } = vi.hoisted(() => ({
  workspaceApiMock: {
    getOrchestration: vi.fn(),
    updateOrchestration: vi.fn(),
  },
  graphApiMock: {
    generateWorker: vi.fn(),
    optimizePrompt: vi.fn(),
  },
  workerApiMock: {
    listCapabilities: vi.fn(),
  },
}))

vi.mock('../utils/workspaceApi', () => ({
  workspaceApi: workspaceApiMock,
}))

vi.mock('../utils/graphApi', () => ({
  graphApi: graphApiMock,
  workerApi: workerApiMock,
}))

describe('WorkspaceOrchestrationEditor', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
    Object.defineProperty(window, 'getComputedStyle', {
      writable: true,
      value: vi.fn().mockImplementation(() => ({
        getPropertyValue: () => '',
      })),
    })
    workerApiMock.listCapabilities.mockResolvedValue([])
    workspaceApiMock.getOrchestration.mockResolvedValue({
      coordinator: {
        id: 'coordinator',
        name: '主控智能体',
        provider: 'anthropic',
        model: 'claude-sonnet-4-6',
        system_prompt: '你是主控',
        llm_profile_id: 'llm-1',
        codex_connection_id: 'codex-1',
        tools: [],
        work_subdir: 'coordinator',
      },
      workers: [],
    })
    workspaceApiMock.updateOrchestration.mockResolvedValue({})
  })

  it('renders the coordinator inline without opening a modal', async () => {
    render(
      <WorkspaceOrchestrationEditor
        workspace={{
          id: 'ws-1',
          kind: 'workspace',
          llm_profiles: [{ id: 'llm-1', name: 'Claude 主力', provider: 'anthropic', model: 'claude-sonnet-4-6', base_url: '' }],
          codex_connections: [{ id: 'codex-1', name: '个人 Codex' }],
        }}
      />,
    )

    expect(await screen.findByLabelText('模型类型')).toBeInTheDocument()
    expect(screen.getByLabelText('API Provider')).toBeInTheDocument()
    expect(screen.queryByLabelText('Codex 模型')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /编\s*辑/ })).not.toBeInTheDocument()
  })

  it('shows codex-only fields after selecting codex runtime type', async () => {
    render(
      <WorkspaceOrchestrationEditor
        workspace={{
          id: 'ws-1',
          kind: 'workspace',
          llm_profiles: [{ id: 'llm-1', name: 'Claude 主力', provider: 'anthropic', model: 'claude-sonnet-4-6', base_url: '' }],
          codex_connections: [{ id: 'codex-1', name: '个人 Codex' }],
        }}
      />,
    )

    fireEvent.mouseDown(await screen.findByLabelText('模型类型'))
    fireEvent.click(await screen.findByText('Codex'))

    expect(await screen.findByPlaceholderText('留空则使用 Codex CLI 默认模型')).toBeInTheDocument()
    expect(screen.getByLabelText('Codex 登录连接')).toBeInTheDocument()
    expect(screen.getByText('建议留空，直接使用当前 Codex CLI 账号默认可用模型；只有明确知道模型权限时再手动填写')).toBeInTheDocument()
  })

  it('hides work subdir for chat coordinator', async () => {
    workspaceApiMock.getOrchestration.mockResolvedValueOnce({
      coordinator: {
        id: 'chat',
        name: '单聊助手',
        provider: 'anthropic',
        model: 'claude-sonnet-4-6',
        system_prompt: '你是单聊助手',
        llm_profile_id: 'llm-1',
        codex_connection_id: '',
        tools: [],
        work_subdir: 'chat',
      },
      workers: [],
    })

    const { container } = render(
      <WorkspaceOrchestrationEditor
        workspace={{
          id: 'ws-chat',
          kind: 'chat',
          llm_profiles: [{ id: 'llm-1', name: 'Claude 主力', provider: 'anthropic', model: 'claude-sonnet-4-6', base_url: '' }],
          codex_connections: [],
        }}
      />,
    )

    expect(await screen.findByText('单聊说明')).toBeInTheDocument()
    expect(screen.getByLabelText('名称')).toHaveValue('单聊助手')
    expect(screen.getByLabelText('API Provider')).toBeInTheDocument()
    expect(screen.getByText('当前目录根')).toBeInTheDocument()
    expect(screen.queryByLabelText('工作子目录')).not.toBeInTheDocument()

    fireEvent.mouseDown(screen.getByLabelText('模型类型'))
    fireEvent.click(await screen.findByText('Codex'))

    expect(await screen.findByLabelText('Codex 模型')).toBeInTheDocument()
    const ids = [...container.querySelectorAll('[id]')].map((element) => element.id).filter(Boolean)
    const duplicateIds = ids.filter((id, index) => ids.indexOf(id) !== index)
    expect(duplicateIds).toEqual([])
  })

  it('switches the inline editor when selecting a worker card', async () => {
    workspaceApiMock.getOrchestration.mockResolvedValueOnce({
      coordinator: {
        id: 'coordinator',
        name: '主控智能体',
        provider: 'anthropic',
        model: 'claude-sonnet-4-6',
        system_prompt: '你是主控',
        llm_profile_id: 'llm-1',
        codex_connection_id: '',
        tools: [],
        work_subdir: 'coordinator',
      },
      workers: [{
        id: 'worker-1',
        name: '前端 Worker',
        provider: 'anthropic',
        model: 'claude-sonnet-4-6',
        system_prompt: '你负责前端实现',
        llm_profile_id: 'llm-1',
        codex_connection_id: '',
        tools: ['ui.render'],
        work_subdir: 'frontend',
        order: 1,
      }],
    })

    render(
      <WorkspaceOrchestrationEditor
        workspace={{
          id: 'ws-1',
          kind: 'workspace',
          llm_profiles: [{ id: 'llm-1', name: 'Claude 主力', provider: 'anthropic', model: 'claude-sonnet-4-6', base_url: '' }],
          codex_connections: [],
        }}
      />,
    )

    expect(await screen.findByDisplayValue('主控智能体')).toBeInTheDocument()

    fireEvent.click(await screen.findByText('#1 前端 Worker'))

    await waitFor(() => {
      expect(screen.getByDisplayValue('前端 Worker')).toBeInTheDocument()
    })
    expect(screen.getByLabelText('工作子目录')).toHaveValue('frontend')
  })
})
