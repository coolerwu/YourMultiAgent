import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import SystemSettings from './SystemSettings'

const { workspaceApiMock } = vi.hoisted(() => ({
  workspaceApiMock: {
    getUpdateNowStatus: vi.fn(),
    getProviderSettings: vi.fn(),
    getAppLog: vi.fn(),
    startUpdateNow: vi.fn(),
    checkCodexConnection: vi.fn(),
    installCodexConnection: vi.fn(),
    loginCodexConnection: vi.fn(),
  },
}))

vi.mock('../utils/workspaceApi', () => ({
  workspaceApi: workspaceApiMock,
}))

describe('SystemSettings', () => {
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  beforeEach(() => {
    vi.useRealTimers()
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
    vi.stubGlobal('location', {
      ...window.location,
      reload: vi.fn(),
    })
    workspaceApiMock.getUpdateNowStatus.mockResolvedValue({
      status: 'idle',
      logs: [],
      steps: [],
      error: '',
    })
    workspaceApiMock.getProviderSettings.mockResolvedValue({
      codex_connections: [
        {
          id: 'codex-1',
          name: '个人 Codex',
          status: 'disconnected',
          install_status: 'installed',
          login_status: 'disconnected',
          cli_version: '0.1.0',
          install_path: '/home/qiuqiu/.local/bin/codex',
          last_error: '',
        },
      ],
    })
    workspaceApiMock.getAppLog.mockResolvedValue({
      filename: 'app.log',
      path: '/tmp/app.log',
      content: '2026-04-08 10:00:00 [INFO] app - ai_request',
      line_count: 12,
      exists: true,
    })
    workspaceApiMock.startUpdateNow.mockResolvedValue({
      status: 'running',
      logs: ['开始执行 Update Now'],
      steps: [{ name: 'git_pull', status: 'running', summary: '' }],
      error: '',
    })
    workspaceApiMock.installCodexConnection.mockResolvedValue({
      message: 'Codex CLI 安装完成。请退出终端并重新进入，然后执行 codex login --device-auth 完成登录。',
      manual_command: 'codex login --device-auth',
      details: '',
    })
  })

  it('starts update now from system settings page', async () => {
    render(<SystemSettings />)

    expect(await screen.findByText('系统设置')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Update Now/ }))
    fireEvent.click(await screen.findByRole('button', { name: '开始更新' }))

    await waitFor(() => {
      expect(workspaceApiMock.startUpdateNow).toHaveBeenCalledTimes(1)
    })

    expect(await screen.findByText('Update Now 执行中')).toBeInTheDocument()
  })

  it('shows codex runtime actions in system settings', async () => {
    render(<SystemSettings />)

    expect((await screen.findAllByText('Codex 运行时')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('个人 Codex')).length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: /更新 Codex/ }))

    await waitFor(() => {
      expect(workspaceApiMock.installCodexConnection).toHaveBeenCalledWith('codex-1')
    })

    expect((await screen.findAllByText('codex login --device-auth')).length).toBeGreaterThan(0)
  })

  it('renders app log inside system settings', async () => {
    render(<SystemSettings />)

    expect(await screen.findByText('应用日志')).toBeInTheDocument()
    expect(await screen.findByText(/当前只保留一个应用日志文件：app\.log/)).toBeInTheDocument()
    expect(await screen.findByTestId('system-app-log')).toHaveTextContent('ai_request')
  })

  it('reloads page after update now succeeds', async () => {
    vi.useRealTimers()
    workspaceApiMock.getUpdateNowStatus
      .mockResolvedValueOnce({
        status: 'idle',
        logs: [],
        steps: [],
        error: '',
      })
      .mockResolvedValueOnce({
        status: 'success',
        logs: ['更新完成'],
        steps: [],
        error: '',
      })

    render(<SystemSettings />)

    fireEvent.click(await screen.findByRole('button', { name: /Update Now/ }))
    fireEvent.click(await screen.findByRole('button', { name: '开始更新' }))

    await waitFor(() => {
      expect(workspaceApiMock.startUpdateNow).toHaveBeenCalledTimes(1)
    })

    await waitFor(() => {
      expect(window.location.reload).toHaveBeenCalledTimes(1)
    }, { timeout: 4000 })
  })

  it('does not reload page for previously completed update status', async () => {
    vi.useRealTimers()
    workspaceApiMock.getUpdateNowStatus.mockResolvedValue({
      status: 'success',
      logs: ['更新完成'],
      steps: [],
      error: '',
    })

    render(<SystemSettings />)

    await screen.findByText('Update Now 已完成')
    await new Promise((resolve) => {
      window.setTimeout(resolve, 2200)
    })

    expect(window.location.reload).not.toHaveBeenCalled()
  })

  it('renders system settings inside its own scroll container', async () => {
    render(<SystemSettings />)

    const container = await screen.findByTestId('system-settings-scroll')
    expect(container).toHaveStyle({ overflowY: 'auto', height: '100%' })
  })
})
