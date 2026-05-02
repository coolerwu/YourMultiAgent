import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Dashboard from './Dashboard'

vi.mock('lottie-react', () => ({
  default: () => <div data-testid="lottie" />,
}))

const { workspaceApiMock } = vi.hoisted(() => ({
  workspaceApiMock: {
    list: vi.fn(),
    update: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
    getOrchestration: vi.fn(),
    listSessions: vi.fn(),
    getSession: vi.fn(),
    createSession: vi.fn(),
    deleteSession: vi.fn(),
    run: vi.fn(),
    updateOrchestration: vi.fn(),
    getProviderSettings: vi.fn(),
    getAppLog: vi.fn(),
    updateProviderSettings: vi.fn(),
    getCodexRuntimeSummary: vi.fn(),
    startUpdateNow: vi.fn(),
    getUpdateNowStatus: vi.fn(),
    checkCodexConnection: vi.fn(),
    installCodexConnection: vi.fn(),
    loginCodexConnection: vi.fn(),
  },
}))

vi.mock('../utils/workspaceApi', () => ({
  workspaceApi: workspaceApiMock,
}))

vi.mock('../utils/graphApi', () => ({
  graphApi: {
    generateWorker: vi.fn(),
    optimizePrompt: vi.fn(),
  },
  workerApi: {
    listCapabilities: vi.fn().mockResolvedValue([]),
  },
}))

describe('Dashboard', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
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

    workspaceApiMock.list.mockResolvedValue([
      {
        id: 'chat-1',
        kind: 'chat',
        name: '单聊示例',
        dir_name: 'chat-demo',
        work_dir: '/tmp/chat-demo',
        llm_profiles: [{
          id: 'llm-1',
          name: 'Claude 主力',
          provider: 'anthropic',
          model: 'claude-sonnet-4-6',
          base_url: '',
          api_key: '',
        }],
        codex_connections: [],
        coordinator: { id: 'chat', name: '单聊助手' },
      },
    ])
    workspaceApiMock.getOrchestration.mockResolvedValue({
      coordinator: {
        id: 'chat',
        name: '单聊助手',
        provider: 'anthropic',
        model: 'claude-sonnet-4-6',
        system_prompt: '你是单聊助手',
        temperature: 0.7,
        max_tokens: 4096,
        tools: [],
        llm_profile_id: 'llm-1',
        codex_connection_id: '',
        base_url: '',
        api_key: '',
        work_subdir: 'chat',
        order: 0,
      },
      workers: [],
    })
    workspaceApiMock.listSessions.mockResolvedValue([])
    workspaceApiMock.getProviderSettings.mockResolvedValue({
      llm_profiles: [],
      codex_connections: [],
    })
    workspaceApiMock.getUpdateNowStatus.mockResolvedValue({
      status: 'idle',
      logs: [],
      steps: [],
      error: '',
    })
    workspaceApiMock.getAppLog.mockResolvedValue({
      filename: 'app.log',
      path: '/tmp/app.log',
      content: '2026-04-08 10:00:00 [INFO] app - ai_request',
      line_count: 12,
      exists: true,
    })
  })

  it('opens chat workspace on runner tab by default', async () => {
    render(<Dashboard />)

    await waitFor(() => {
      expect(workspaceApiMock.list).toHaveBeenCalled()
    })

    expect(await screen.findByRole('tab', { name: '配置' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '运行' })).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Worker' })).not.toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '运行' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByText('当前目录中的历史会话、compact 摘要和 memory 会持续复用。', {}, { timeout: 5000 })).toBeInTheDocument()
  })

  it('still exposes configuration tab for chat workspace', async () => {
    render(<Dashboard />)

    await waitFor(() => {
      expect(workspaceApiMock.list).toHaveBeenCalled()
    })

    fireEvent.click(await screen.findByRole('tab', { name: '配置' }))

    expect(await screen.findByText('单聊助手')).toBeInTheDocument()
    expect(screen.getByLabelText('名称')).toHaveValue('单聊助手')
    expect(screen.queryByRole('button', { name: /编\s*辑/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '保存编排配置' })).toBeInTheDocument()
  })

  it('shows app log as a sibling panel of system settings', async () => {
    render(<Dashboard />)

    await waitFor(() => {
      expect(workspaceApiMock.list).toHaveBeenCalled()
    })

    fireEvent.click(await screen.findByText('应用日志'))

    expect(await screen.findByText(/当前只保留一个应用日志文件：app\.log/)).toBeInTheDocument()
    expect(await screen.findByTestId('system-app-log')).toHaveTextContent('ai_request')
  })

  it('collapses desktop sidebar to icon mode and persists preference', async () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query) => ({
        matches: query.includes('min-width'),
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })

    render(<Dashboard />)

    await waitFor(() => {
      expect(workspaceApiMock.list).toHaveBeenCalled()
    })

    const chatSectionMatcher = (_, element) => element?.textContent?.replace(/\s+/g, ' ').trim() === '单聊目录 (1)'
    await waitFor(() => {
      expect(screen.getAllByText(chatSectionMatcher).length).toBeGreaterThan(0)
    })
    fireEvent.click(screen.getByRole('button', { name: '折叠导航' }))

    await waitFor(() => {
      expect(screen.queryAllByText(chatSectionMatcher)).toHaveLength(0)
    })

    expect(window.localStorage.getItem('dashboard-sidebar-collapsed')).toBe('1')
    expect(screen.getByRole('button', { name: '展开导航' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '全局模型连接' })).toBeInTheDocument()
  })
})
