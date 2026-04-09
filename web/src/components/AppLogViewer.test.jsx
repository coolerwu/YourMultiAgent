import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AppLogViewer from './AppLogViewer'

const { workspaceApiMock } = vi.hoisted(() => ({
  workspaceApiMock: {
    getAppLog: vi.fn(),
  },
}))

vi.mock('../utils/workspaceApi', () => ({
  workspaceApi: workspaceApiMock,
}))

describe('AppLogViewer', () => {
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    workspaceApiMock.getAppLog.mockResolvedValue({
      filename: 'app.log',
      path: '/tmp/app.log',
      content: '2026-04-08 10:00:00 [INFO] app - ai_request',
      line_count: 12,
      exists: true,
    })
  })

  it('renders app log as a standalone page', async () => {
    render(<AppLogViewer />)

    expect(await screen.findByText('应用全链路日志')).toBeInTheDocument()
    expect(await screen.findByText(/当前只保留一个应用日志文件：app\.log/)).toBeInTheDocument()
    expect(await screen.findByTestId('system-app-log')).toHaveTextContent('ai_request')
  })

  it('filters log content by keyword', async () => {
    workspaceApiMock.getAppLog.mockResolvedValueOnce({
      filename: 'app.log',
      path: '/tmp/app.log',
      content: 'line-1 ai_request\nline-2 ai_error',
      line_count: 2,
      exists: true,
    })
    render(<AppLogViewer />)

    expect(await screen.findByTestId('system-app-log')).toHaveTextContent('ai_request')
    fireEvent.change(
      screen.getByPlaceholderText('搜索日志关键字（区分大小写关闭）'),
      { target: { value: 'ai_error' } },
    )
    expect(screen.getByTestId('system-app-log')).toHaveTextContent('ai_error')
    expect(screen.getByTestId('system-app-log')).not.toHaveTextContent('ai_request')
  })

  it('refreshes automatically on interval', async () => {
    const setIntervalSpy = vi.spyOn(window, 'setInterval').mockImplementation((handler) => {
      if (typeof handler === 'function') handler()
      return 1
    })
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval').mockImplementation(() => {})
    render(<AppLogViewer />)
    expect(await screen.findByText('应用全链路日志')).toBeInTheDocument()

    await waitFor(() => {
      expect(workspaceApiMock.getAppLog).toHaveBeenCalledTimes(2)
    })
    setIntervalSpy.mockRestore()
    clearIntervalSpy.mockRestore()
  })
})
