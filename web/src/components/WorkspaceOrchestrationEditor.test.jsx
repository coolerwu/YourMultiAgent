import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorkspaceOrchestrationEditor from './WorkspaceOrchestrationEditor'

async function clickCoordinatorEdit() {
  const editButtons = await screen.findAllByRole('button', { name: /编\s*辑/ })
  fireEvent.click(editButtons[0])
}

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
        llm_profile_id: '',
        codex_connection_id: 'codex-1',
        tools: [],
        work_subdir: 'coordinator',
      },
      workers: [],
    })
    workspaceApiMock.updateOrchestration.mockResolvedValue({})
  })

  it('keeps stale codex connection on llm nodes out of codex mode', async () => {
    render(
      <WorkspaceOrchestrationEditor
        workspace={{
          id: 'ws-1',
          kind: 'workspace',
          llm_profiles: [],
          codex_connections: [{ id: 'codex-1', name: '个人 Codex' }],
        }}
      />,
    )

    await clickCoordinatorEdit()

    expect(await screen.findByLabelText('模型类型')).toBeInTheDocument()
    expect(screen.getByLabelText('Provider')).toBeInTheDocument()
    expect(screen.queryByLabelText('Codex 模型')).not.toBeInTheDocument()
    expect(screen.queryByText('通用 LLM 配置')).not.toBeInTheDocument()
  })

  it('shows codex-only fields after selecting codex runtime type', async () => {
    render(
      <WorkspaceOrchestrationEditor
        workspace={{
          id: 'ws-1',
          kind: 'workspace',
          llm_profiles: [],
          codex_connections: [{ id: 'codex-1', name: '个人 Codex' }],
        }}
      />,
    )

    await clickCoordinatorEdit()

    fireEvent.mouseDown(screen.getByLabelText('模型类型'))
    fireEvent.click(await screen.findByText('Codex'))

    expect(await screen.findByPlaceholderText('留空则使用 Codex CLI 默认模型')).toBeInTheDocument()
    expect(screen.getByLabelText('Codex 登录连接')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('留空则使用 Codex CLI 默认模型')).toHaveAttribute(
      'placeholder',
      '留空则使用 Codex CLI 默认模型',
    )
    expect(
      screen.getByText('建议留空，直接使用当前 Codex CLI 账号默认可用模型；只有明确知道模型权限时再手动填写'),
    ).toBeInTheDocument()
  })

  it('hides work subdir for chat coordinator', async () => {
    workspaceApiMock.getOrchestration.mockResolvedValueOnce({
      coordinator: {
        id: 'chat',
        name: '单聊助手',
        provider: 'anthropic',
        model: 'claude-sonnet-4-6',
        system_prompt: '你是单聊助手',
        llm_profile_id: '',
        codex_connection_id: '',
        tools: [],
        work_subdir: 'chat',
      },
      workers: [],
    })

    render(
      <WorkspaceOrchestrationEditor
        workspace={{
          id: 'ws-chat',
          kind: 'chat',
          llm_profiles: [],
          codex_connections: [],
        }}
      />,
    )

    expect(await screen.findByText('当前目录根')).toBeInTheDocument()
    expect(screen.queryByText(/^chat$/)).not.toBeInTheDocument()
  })
})
