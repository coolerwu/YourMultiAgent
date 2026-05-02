import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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
  afterEach(() => {
    cleanup()
  })

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

    expect(screen.getByRole('combobox')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /新建会话/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /删除会话/ })).toBeInTheDocument()
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

  it('keeps long summary, memory and message content wrappable', async () => {
    const longToken = 'need_clarification:true:' + 'AuthorizationXApiKey'.repeat(20)
    workspaceApiMock.listSessions.mockResolvedValue([
      {
        id: 'session-1',
        title: '历史会话',
        updated_at: '2026-04-07T10:00:00Z',
        message_count: 2,
        summary: longToken,
        memory_items: [{ id: 'memory-1', category: 'artifact', content: longToken }],
        messages: [],
      },
    ])
    workspaceApiMock.getSession.mockResolvedValue({
      id: 'session-1',
      title: '历史会话',
      updated_at: '2026-04-07T10:00:00Z',
      message_count: 2,
      summary: longToken,
      memory_items: [{ id: 'memory-1', category: 'artifact', content: longToken }],
      messages: [
        { id: 'msg-1', role: 'error', kind: 'error', content: longToken, created_at: '2026-04-07T10:01:00Z' },
      ],
    })

    render(<WorkspaceRunView workspace={{ id: 'ws-1', llm_profiles: [] }} />)

    const summary = await screen.findByTestId('session-summary')
    const memoryItems = await screen.findAllByTestId('memory-item-memory-1')
    const messages = await screen.findAllByTestId('message-content-0')
    const memory = memoryItems.at(-1)
    const message = messages.at(-1)

    expect(summary.getAttribute('style')).toContain('overflow-wrap: anywhere')
    expect(summary.getAttribute('style')).toContain('word-break: break-word')
    expect(memory?.getAttribute('style')).toContain('overflow-wrap: anywhere')
    expect(memory?.getAttribute('style')).toContain('max-width: 100%')
    expect(message?.getAttribute('style')).toContain('overflow-wrap: anywhere')
    expect(message?.getAttribute('style')).toContain('word-break: break-word')
    expect(message?.getAttribute('style')).toContain('min-width: 0')
  })

  it('renders streamed step_changed events and current step on agent card', async () => {
    workspaceApiMock.run.mockImplementation(async (_workspaceId, _payload, onChunk) => {
      onChunk({ type: 'worker_start', node: 'worker-1', node_name: '研发', actor_name: '研发' })
      onChunk({ type: 'step_changed', node: 'worker-1', node_name: '研发', actor_name: '研发', step: 'execute' })
    })

    render(<WorkspaceRunView workspace={{ id: 'ws-1', llm_profiles: [] }} />)

    await waitFor(() => {
      expect(workspaceApiMock.getSession).toHaveBeenCalledWith('ws-1', 'session-1')
    })
    const input = screen.getByPlaceholderText('输入任务，交给主控智能体...（Ctrl+Enter 发送）')
    fireEvent.change(input, { target: { value: '实现页面' } })
    fireEvent.click(screen.getByRole('button', { name: /发送/ }))

    expect(await screen.findByText('进入步骤：执行')).toBeInTheDocument()
    expect(await screen.findByTestId('agent-step-worker-1')).toHaveTextContent('Step: 执行')
  })

  it('renders streamed run task DAG state', async () => {
    workspaceApiMock.run.mockImplementation(async (_workspaceId, _payload, onChunk) => {
      onChunk({ type: 'run_started', run_id: 'run-1', status: 'running', actor_name: '主控' })
      onChunk({
        type: 'plan_created',
        run_id: 'run-1',
        coordinator_name: '主控',
        tasks: [
          { id: 'task-1', worker_id: 'worker-1', worker_name: '研发', instruction: '实现页面', dependencies: [] },
        ],
      })
      onChunk({ type: 'task_started', task_id: 'task-1', worker_id: 'worker-1', worker_name: '研发', instruction: '实现页面', actor_name: '研发' })
      onChunk({ type: 'artifact_recorded', task_id: 'task-1', path: 'shared/page.md', description: '页面说明', actor_name: '研发' })
      onChunk({ type: 'task_finished', task_id: 'task-1', worker_id: 'worker-1', worker_name: '研发', summary: '已完成页面', actor_name: '研发' })
      onChunk({ type: 'run_finished', run_id: 'run-1', status: 'succeeded', summary: '全部完成', actor_name: '主控' })
    })

    render(<WorkspaceRunView workspace={{ id: 'ws-1', llm_profiles: [] }} />)

    await waitFor(() => {
      expect(workspaceApiMock.getSession).toHaveBeenCalledWith('ws-1', 'session-1')
    })
    const input = screen.getByPlaceholderText('输入任务，交给主控智能体...（Ctrl+Enter 发送）')
    fireEvent.change(input, { target: { value: '实现页面' } })
    fireEvent.click(screen.getByRole('button', { name: /发送/ }))

    expect(await screen.findByTestId('run-task-panel')).toBeInTheDocument()
    expect(await screen.findByText('task-1')).toBeInTheDocument()
    expect((await screen.findAllByText(/实现页面/)).length).toBeGreaterThan(0)
    expect(await screen.findByText(/shared\/page.md/)).toBeInTheDocument()
    expect(await screen.findByText(/全部完成/)).toBeInTheDocument()
  })

  it('switches session from top dropdown', async () => {
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
      {
        id: 'session-2',
        title: '近期会话',
        updated_at: '2026-04-08T10:00:00Z',
        message_count: 4,
        summary: '已经定位到 Codex 输出问题。',
        memory_items: [{ id: 'memory-2', category: 'artifact', content: 'codex_cli_adapter.py' }],
        messages: [],
      },
    ])
    workspaceApiMock.getSession.mockImplementation(async (_workspaceId, sessionId) => {
      if (sessionId === 'session-2') {
        return {
          id: 'session-2',
          title: '近期会话',
          updated_at: '2026-04-08T10:00:00Z',
          message_count: 4,
          summary: '已经定位到 Codex 输出问题。',
          memory_items: [{ id: 'memory-2', category: 'artifact', content: 'codex_cli_adapter.py' }],
          messages: [
            { id: 'msg-3', role: 'assistant', kind: 'assistant', content: '最终回答正文', actor_name: '单聊助手', created_at: '2026-04-08T10:01:00Z' },
          ],
        }
      }
      return {
        id: 'session-1',
        title: '历史会话',
        updated_at: '2026-04-07T10:00:00Z',
        message_count: 2,
        summary: '此前已经确定页面结构。',
        memory_items: [{ id: 'memory-1', category: 'goal', content: '做一个页面' }],
        messages: [
          { id: 'msg-1', role: 'user', kind: 'user', content: '做一个页面', created_at: '2026-04-07T10:00:00Z' },
        ],
      }
    })

    render(<WorkspaceRunView workspace={{ id: 'chat-1', kind: 'chat', name: 'PetTrace', coordinator: { id: 'chat', name: '单聊助手' }, llm_profiles: [] }} />)

    await waitFor(() => {
      expect(workspaceApiMock.listSessions).toHaveBeenCalledWith('chat-1')
    })

    fireEvent.mouseDown(screen.getByRole('combobox'))
    fireEvent.click(await screen.findByText(/近期会话/))

    await waitFor(() => {
      expect(workspaceApiMock.getSession).toHaveBeenCalledWith('chat-1', 'session-2')
    })

    expect(await screen.findByText('artifact: codex_cli_adapter.py')).toBeInTheDocument()
    expect(await screen.findByText('最终回答正文')).toBeInTheDocument()
  })
})
