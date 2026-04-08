import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
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
        model: '',
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

  it('shows codex model hint when coordinator uses a codex connection', async () => {
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

    fireEvent.click(await screen.findByRole('button', { name: /编\s*辑/ }))

    expect(await screen.findByLabelText('Codex 模型')).toHaveAttribute(
      'placeholder',
      '留空则使用 Codex CLI 默认模型',
    )
    expect(
      screen.getByText('建议留空，直接使用当前 Codex CLI 账号默认可用模型；只有明确知道模型权限时再手动填写'),
    ).toBeInTheDocument()
  })
})
