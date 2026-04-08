import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorkspaceRunView from './WorkspaceRunView'

vi.mock('lottie-react', () => ({
  default: () => <div data-testid="lottie" />,
}))

const { workspaceApiMock } = vi.hoisted(() => ({
  workspaceApiMock: {
    getOrchestration: vi.fn(),
    listSessions: vi.fn(),
    getSession: vi.fn(),
    createSession: vi.fn(),
    deleteSession: vi.fn(),
    run: vi.fn(),
  },
}))

vi.mock('../utils/workspaceApi', () => ({
  workspaceApi: workspaceApiMock,
}))

describe('WorkspaceRunView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    workspaceApiMock.getOrchestration.mockResolvedValue({
      coordinator: { id: 'coordinator', name: '主控' },
      workers: [{ id: 'worker-1', name: '研发', model: 'gpt-4o', order: 1, llm_profile_id: '' }],
    })
    workspaceApiMock.listSessions.mockResolvedValue([
      {
        id: 'session-1',
        title: '历史会话',
        updated_at: '2026-04-07T10:00:00Z',
        message_count: 2,
        summary: '此前已经确定页面结构。',
        memory_items: [{ id: 'memory-1', category: 'goal', content: '做一个页面' }],
        messages: [],
      },
    ])
    workspaceApiMock.getSession.mockResolvedValue({
      id: 'session-1',
      title: '历史会话',
      updated_at: '2026-04-07T10:00:00Z',
      message_count: 2,
      summary: '此前已经确定页面结构。',
      memory_items: [{ id: 'memory-1', category: 'goal', content: '做一个页面' }],
      messages: [
        { id: 'msg-1', role: 'user', kind: 'user', content: '做一个页面', created_at: '2026-04-07T10:00:00Z' },
        { id: 'msg-2', role: 'assistant', kind: 'summary', content: '页面结构已确认', actor_name: '主控智能体', created_at: '2026-04-07T10:01:00Z' },
      ],
    })
  })

  it('loads sessions and renders stored conversation context', async () => {
    render(<WorkspaceRunView workspace={{ id: 'ws-1', llm_profiles: [] }} />)

    await waitFor(() => {
      expect(workspaceApiMock.listSessions).toHaveBeenCalledWith('ws-1')
    })

    expect(await screen.findByText('历史会话')).toBeInTheDocument()
    expect(await screen.findByText(/Compact 摘要/)).toBeInTheDocument()
    expect(await screen.findByText('goal: 做一个页面')).toBeInTheDocument()
    expect(await screen.findByText('页面结构已确认')).toBeInTheDocument()
  })

  it('renders chat-specific copy for chat workspace', async () => {
    render(<WorkspaceRunView workspace={{ id: 'chat-1', kind: 'chat', name: 'PetTrace', coordinator: { id: 'chat', name: '单聊助手' }, llm_profiles: [] }} />)

    await waitFor(() => {
      expect(workspaceApiMock.listSessions).toHaveBeenCalledWith('chat-1')
    })

    expect(screen.getByText('PetTrace')).toBeInTheDocument()
    expect(screen.getByText('当前目录中的历史会话、compact 摘要和 memory 会持续复用。')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('输入消息...（Ctrl+Enter 发送）')).toBeInTheDocument()
    expect(workspaceApiMock.getOrchestration).not.toHaveBeenCalled()
  })
})
